import os
import uuid
import logging
import shutil
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import desc
from pydantic import BaseModel
from typing import List, Optional, Dict, Any

from app.database import get_db
from app.auth import get_current_user
from app.models import ChatSession, ChatMessage, ChatFile, ChatContext, ChatFeedback
from app.services.chat.chat_service import ChatService
from app.rate_limiter import rate_limit


logger = logging.getLogger(__name__)
router = APIRouter(tags=["chat"])
chat_service = ChatService()

# Directory to save chat uploaded documents
UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "static", "chat_uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Pydantic Schemas for inputs
class ChatMessageInput(BaseModel):
    session_id: Optional[str] = None
    message: str

class ChatSessionRename(BaseModel):
    session_id: str
    title: str

class ChatFeedbackInput(BaseModel):
    message_id: str
    rating: int  # 1 for thumbs up, -1 for thumbs down
    comment: Optional[str] = None

class ChatSessionRegenerateInput(BaseModel):
    session_id: str


@router.post("/api/chat")
async def send_chat_message(
    payload: ChatMessageInput,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    _rl: None = Depends(rate_limit(limit=30, window_seconds=60))
):
    """
    Core conversation streaming handler. Initiates or resumes a chat session,
    persists messages, and streams the assistant response using SSE / streaming response.
    """
    if current_user.get("sub") == "guest_user":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    
    user_id = current_user.get("sub")
    user_email = current_user.get("email") or "student@auraroutes.com"
    session_id = payload.session_id

    # Create new session if none provided
    if not session_id:
        session_title = payload.message[:40] + "..." if len(payload.message) > 40 else payload.message
        session = ChatSession(
            user_id=user_id,
            title=session_title,
            is_pinned=False
        )
        db.add(session)
        db.commit()
        db.refresh(session)
        session_id = session.id

        # Auto-initialize Chat Context snapshot
        context = ChatContext(session_id=session_id)
        db.add(context)
        db.commit()
    else:
        # Verify session ownership
        session = db.query(ChatSession).filter(ChatSession.id == session_id, ChatSession.user_id == user_id).first()
        if not session:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat session not found")

    # Save User message to db
    user_msg = ChatMessage(
        session_id=session_id,
        role="user",
        content=payload.message
    )
    db.add(user_msg)
    
    # Touch session timestamp
    session.title = session.title  # Keeps the title unchanged but updates trigger if needed
    db.commit()

    # Get conversation history
    history = db.query(ChatMessage).filter(ChatMessage.session_id == session_id).order_by(ChatMessage.created_at).all()

    # Async generator to stream OpenAI chunks and save full text on completion
    async def response_streamer():
        accumulated_chunks = []
        try:
            # Yield session info in custom headers/chunks at start
            yield f"[SESSION_ID:{session_id}]"

            # Call async ChatService
            async for chunk in chat_service.get_streaming_response(
                db=db,
                session_id=session_id,
                user_id=user_id,
                user_email=user_email,
                history=history[:-1],  # Exclude current message since we pass it explicitly
                new_user_message_content=payload.message
            ):
                accumulated_chunks.append(chunk)
                yield chunk

        finally:
            # Save accumulated response to database once client stream finishes
            if accumulated_chunks:
                full_reply = "".join(accumulated_chunks)
                # Ensure we don't save error codes as AI replies
                if not full_reply.startswith("[AI Service Error]"):
                    db_session = next(get_db())
                    try:
                        ai_msg = ChatMessage(
                            session_id=session_id,
                            role="assistant",
                            content=full_reply
                        )
                        db_session.add(ai_msg)
                        db_session.commit()
                    except Exception as db_err:
                        logger.error(f"Failed to persist streamed response to db: {str(db_err)}")
                    finally:
                        db_session.close()

    return StreamingResponse(response_streamer(), media_type="text/plain")


@router.post("/api/chat/upload")
def upload_chat_file(
    session_id: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Uploads reference document (PDF/Image) for a specific chat session.
    """
    if current_user.get("sub") == "guest_user":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    
    user_id = current_user.get("sub")
    session = db.query(ChatSession).filter(ChatSession.id == session_id, ChatSession.user_id == user_id).first()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat session not found")

    # Generate unique filename
    unique_fn = f"{uuid.uuid4()}_{file.filename}"
    dest_path = os.path.join(UPLOAD_DIR, unique_fn)

    # Save file to disk
    try:
        with open(dest_path, "wb") as f:
            shutil.copyfileobj(file.file, f)
    except Exception as e:
        logger.error(f"Failed to save upload file: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to save file on server")

    # Save reference in database
    db_file = ChatFile(
        session_id=session_id,
        filename=file.filename,
        file_type=file.content_type or "application/octet-stream",
        file_path=f"/static/chat_uploads/{unique_fn}",
        file_size=os.path.getsize(dest_path)
    )
    db.add(db_file)
    db.commit()
    db.refresh(db_file)

    return {
        "message": "File uploaded successfully",
        "file": {
            "id": db_file.id,
            "filename": db_file.filename,
            "file_type": db_file.file_type,
            "file_size": db_file.file_size
        }
    }


@router.get("/api/chat/history")
def get_chat_history(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Gathers list of previous user chat sessions, prioritizing pinned conversations.
    """
    if current_user.get("sub") == "guest_user":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    
    user_id = current_user.get("sub")
    sessions = db.query(ChatSession).filter(
        ChatSession.user_id == user_id
    ).order_by(
        desc(ChatSession.is_pinned),
        desc(ChatSession.updated_at)
    ).all()

    return [
        {
            "id": s.id,
            "title": s.title,
            "is_pinned": s.is_pinned,
            "is_favorite": s.is_favorite,
            "is_archived": s.is_archived,
            "created_at": s.created_at.isoformat() if s.created_at else None,
            "updated_at": s.updated_at.isoformat() if s.updated_at else None
        }
        for s in sessions
    ]


@router.get("/api/chat/{id}")
def get_chat_session_details(
    id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Retrieves full details of a specific chat session (messages list + files list).
    """
    if current_user.get("sub") == "guest_user":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    
    user_id = current_user.get("sub")
    session = db.query(ChatSession).filter(ChatSession.id == id, ChatSession.user_id == user_id).first()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat session not found")

    messages = db.query(ChatMessage).filter(ChatMessage.session_id == id).order_by(ChatMessage.created_at).all()
    files = db.query(ChatFile).filter(ChatFile.session_id == id).all()

    return {
        "session": {
            "id": session.id,
            "title": session.title,
            "is_pinned": session.is_pinned,
            "is_favorite": session.is_favorite,
            "is_archived": session.is_archived
        },
        "messages": [
            {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "created_at": m.created_at.isoformat() if m.created_at else None,
                "feedbacks": [
                    {"rating": f.rating, "comment": f.comment} for f in m.feedbacks
                ]
            }
            for m in messages
        ],
        "files": [
            {
                "id": f.id,
                "filename": f.filename,
                "file_type": f.file_type,
                "file_path": f.file_path,
                "file_size": f.file_size
            }
            for f in files
        ]
    }


@router.delete("/api/chat/{id}")
def delete_chat_session(
    id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Deletes a conversation session from records.
    """
    if current_user.get("sub") == "guest_user":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    
    user_id = current_user.get("sub")
    session = db.query(ChatSession).filter(ChatSession.id == id, ChatSession.user_id == user_id).first()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat session not found")

    db.delete(session)
    db.commit()
    return {"message": "Chat session deleted successfully."}


@router.put("/api/chat/rename")
def rename_chat_session(
    payload: ChatSessionRename,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Renames session title.
    """
    if current_user.get("sub") == "guest_user":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    
    user_id = current_user.get("sub")
    session = db.query(ChatSession).filter(ChatSession.id == payload.session_id, ChatSession.user_id == user_id).first()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat session not found")

    session.title = payload.title
    db.commit()
    return {"message": "Chat session renamed.", "title": session.title}


@router.post("/api/chat/feedback")
def submit_message_feedback(
    payload: ChatFeedbackInput,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Records thumbs rating and review text feedback for an assistant response.
    """
    if current_user.get("sub") == "guest_user":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    
    user_id = current_user.get("sub")
    message = db.query(ChatMessage).join(ChatSession).filter(
        ChatMessage.id == payload.message_id,
        ChatSession.user_id == user_id
    ).first()

    if not message:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")

    # Add or update feedback
    feedback = db.query(ChatFeedback).filter(ChatFeedback.message_id == payload.message_id).first()
    if not feedback:
        feedback = ChatFeedback(
            message_id=payload.message_id,
            rating=payload.rating,
            comment=payload.comment
        )
        db.add(feedback)
    else:
        feedback.rating = payload.rating
        feedback.comment = payload.comment
    
    db.commit()
    return {"message": "Feedback submitted successfully."}


@router.post("/api/chat/regenerate")
async def regenerate_chat_message(
    payload: ChatSessionRegenerateInput,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Deletes last assistant message and streams new response for last user message.
    """
    if current_user.get("sub") == "guest_user":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    
    user_id = current_user.get("sub")
    user_email = current_user.get("email") or "student@auraroutes.com"
    session_id = payload.session_id

    session = db.query(ChatSession).filter(ChatSession.id == session_id, ChatSession.user_id == user_id).first()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat session not found")

    # Fetch last message
    last_msg = db.query(ChatMessage).filter(ChatMessage.session_id == session_id).order_by(desc(ChatMessage.created_at)).first()
    if not last_msg:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No messages in conversation to regenerate.")

    # If last message was assistant, delete it
    if last_msg.role == "assistant":
        db.delete(last_msg)
        db.commit()
        # Re-fetch user message
        last_user_msg = db.query(ChatMessage).filter(ChatMessage.session_id == session_id, ChatMessage.role == "user").order_by(desc(ChatMessage.created_at)).first()
    else:
        last_user_msg = last_msg

    if not last_user_msg:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No user message found to regenerate response.")

    history = db.query(ChatMessage).filter(ChatMessage.session_id == session_id).order_by(ChatMessage.created_at).all()

    async def response_streamer():
        accumulated_chunks = []
        try:
            async for chunk in chat_service.get_streaming_response(
                db=db,
                session_id=session_id,
                user_id=user_id,
                user_email=user_email,
                history=history[:-1] if last_msg.role == "assistant" else history,
                new_user_message_content=last_user_msg.content
            ):
                accumulated_chunks.append(chunk)
                yield chunk
        finally:
            if accumulated_chunks:
                full_reply = "".join(accumulated_chunks)
                if not full_reply.startswith("[AI Service Error]"):
                    db_session = next(get_db())
                    try:
                        ai_msg = ChatMessage(
                            session_id=session_id,
                            role="assistant",
                            content=full_reply
                        )
                        db_session.add(ai_msg)
                        db_session.commit()
                    except Exception as db_err:
                        logger.error(f"Failed to persist regenerated streamed response: {str(db_err)}")
                    finally:
                        db_session.close()

    return StreamingResponse(response_streamer(), media_type="text/plain")


@router.put("/api/chat/pin/{id}")
def pin_chat_session(
    id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Toggles is_pinned status of a conversation. Pinned conversations appear first in list.
    """
    if current_user.get("sub") == "guest_user":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    
    user_id = current_user.get("sub")
    session = db.query(ChatSession).filter(ChatSession.id == id, ChatSession.user_id == user_id).first()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat session not found")

    session.is_pinned = not session.is_pinned
    db.commit()
    return {"message": "Chat session pin toggled.", "is_pinned": session.is_pinned}
