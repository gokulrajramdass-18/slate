"""
SMTP Configuration API endpoints
"""
from typing import Optional
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, EmailStr
from datetime import datetime
from open_notebook.database.repository import repo_query, repo_execute
from api.services.smtp_service import SMTPService

router = APIRouter(prefix="/api/smtp", tags=["smtp"])


class SMTPConfigCreate(BaseModel):
    smtp_host: str
    smtp_port: int
    smtp_username: str
    smtp_password: str
    smtp_from_email: EmailStr
    smtp_from_name: Optional[str] = "Open Notebook"
    smtp_use_tls: bool = True
    smtp_use_ssl: bool = False


class SMTPConfigUpdate(BaseModel):
    smtp_host: Optional[str] = None
    smtp_port: Optional[int] = None
    smtp_username: Optional[str] = None
    smtp_password: Optional[str] = None
    smtp_from_email: Optional[EmailStr] = None
    smtp_from_name: Optional[str] = None
    smtp_use_tls: Optional[bool] = None
    smtp_use_ssl: Optional[bool] = None
    is_active: Optional[bool] = None


class SMTPConfigResponse(BaseModel):
    id: str
    smtp_host: str
    smtp_port: int
    smtp_username: str
    smtp_from_email: str
    smtp_from_name: Optional[str]
    smtp_use_tls: bool
    smtp_use_ssl: bool
    is_active: bool
    created: str
    updated: str
    # Note: password is not returned in responses


class SMTPTestRequest(BaseModel):
    test_email: EmailStr


@router.get("/config", response_model=Optional[SMTPConfigResponse])
async def get_smtp_config():
    """Get current SMTP configuration (without password)"""
    query = "SELECT * FROM smtp_config WHERE id = 'default'"
    results = await repo_query(query)

    if not results:
        return None

    config = results[0]
    # Don't return password
    return SMTPConfigResponse(
        id=config["id"],
        smtp_host=config["smtp_host"],
        smtp_port=config["smtp_port"],
        smtp_username=config["smtp_username"],
        smtp_from_email=config["smtp_from_email"],
        smtp_from_name=config.get("smtp_from_name"),
        smtp_use_tls=bool(config["smtp_use_tls"]),
        smtp_use_ssl=bool(config["smtp_use_ssl"]),
        is_active=bool(config["is_active"]),
        created=config["created"],
        updated=config["updated"],
    )


@router.post("/config", response_model=SMTPConfigResponse, status_code=status.HTTP_201_CREATED)
async def create_or_update_smtp_config(config_data: SMTPConfigCreate):
    """Create or update SMTP configuration"""
    # Check if config exists
    check_query = "SELECT * FROM smtp_config WHERE id = 'default'"
    existing = await repo_query(check_query)

    now = datetime.utcnow().isoformat()

    if existing:
        # Update existing
        update_query = """
            UPDATE smtp_config SET
                smtp_host = :smtp_host,
                smtp_port = :smtp_port,
                smtp_username = :smtp_username,
                smtp_password = :smtp_password,
                smtp_from_email = :smtp_from_email,
                smtp_from_name = :smtp_from_name,
                smtp_use_tls = :smtp_use_tls,
                smtp_use_ssl = :smtp_use_ssl,
                updated = :updated
            WHERE id = 'default'
        """
        await repo_execute(update_query, {
            "smtp_host": config_data.smtp_host,
            "smtp_port": config_data.smtp_port,
            "smtp_username": config_data.smtp_username,
            "smtp_password": config_data.smtp_password,
            "smtp_from_email": config_data.smtp_from_email,
            "smtp_from_name": config_data.smtp_from_name,
            "smtp_use_tls": int(config_data.smtp_use_tls),
            "smtp_use_ssl": int(config_data.smtp_use_ssl),
            "updated": now,
        })
    else:
        # Create new
        insert_query = """
            INSERT INTO smtp_config (
                id, smtp_host, smtp_port, smtp_username, smtp_password,
                smtp_from_email, smtp_from_name, smtp_use_tls, smtp_use_ssl,
                is_active, created, updated
            ) VALUES (
                'default', :smtp_host, :smtp_port, :smtp_username, :smtp_password,
                :smtp_from_email, :smtp_from_name, :smtp_use_tls, :smtp_use_ssl,
                1, :created, :updated
            )
        """
        await repo_execute(insert_query, {
            "smtp_host": config_data.smtp_host,
            "smtp_port": config_data.smtp_port,
            "smtp_username": config_data.smtp_username,
            "smtp_password": config_data.smtp_password,
            "smtp_from_email": config_data.smtp_from_email,
            "smtp_from_name": config_data.smtp_from_name,
            "smtp_use_tls": int(config_data.smtp_use_tls),
            "smtp_use_ssl": int(config_data.smtp_use_ssl),
            "created": now,
            "updated": now,
        })

    # Return the config (without password)
    return SMTPConfigResponse(
        id="default",
        smtp_host=config_data.smtp_host,
        smtp_port=config_data.smtp_port,
        smtp_username=config_data.smtp_username,
        smtp_from_email=config_data.smtp_from_email,
        smtp_from_name=config_data.smtp_from_name,
        smtp_use_tls=config_data.smtp_use_tls,
        smtp_use_ssl=config_data.smtp_use_ssl,
        is_active=True,
        created=existing[0]["created"] if existing else now,
        updated=now,
    )


@router.put("/config", response_model=SMTPConfigResponse)
async def update_smtp_config(update_data: SMTPConfigUpdate):
    """Partially update SMTP configuration"""
    # Check if config exists
    check_query = "SELECT * FROM smtp_config WHERE id = 'default'"
    existing = await repo_query(check_query)

    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="SMTP configuration not found. Create one first."
        )

    # Build update query dynamically
    updates = []
    params = {"updated": datetime.utcnow().isoformat()}

    if update_data.smtp_host is not None:
        updates.append("smtp_host = :smtp_host")
        params["smtp_host"] = update_data.smtp_host

    if update_data.smtp_port is not None:
        updates.append("smtp_port = :smtp_port")
        params["smtp_port"] = update_data.smtp_port

    if update_data.smtp_username is not None:
        updates.append("smtp_username = :smtp_username")
        params["smtp_username"] = update_data.smtp_username

    if update_data.smtp_password is not None:
        updates.append("smtp_password = :smtp_password")
        params["smtp_password"] = update_data.smtp_password

    if update_data.smtp_from_email is not None:
        updates.append("smtp_from_email = :smtp_from_email")
        params["smtp_from_email"] = update_data.smtp_from_email

    if update_data.smtp_from_name is not None:
        updates.append("smtp_from_name = :smtp_from_name")
        params["smtp_from_name"] = update_data.smtp_from_name

    if update_data.smtp_use_tls is not None:
        updates.append("smtp_use_tls = :smtp_use_tls")
        params["smtp_use_tls"] = int(update_data.smtp_use_tls)

    if update_data.smtp_use_ssl is not None:
        updates.append("smtp_use_ssl = :smtp_use_ssl")
        params["smtp_use_ssl"] = int(update_data.smtp_use_ssl)

    if update_data.is_active is not None:
        updates.append("is_active = :is_active")
        params["is_active"] = int(update_data.is_active)

    updates.append("updated = :updated")

    if len(updates) > 1:  # More than just 'updated'
        query = f"UPDATE smtp_config SET {', '.join(updates)} WHERE id = 'default'"
        await repo_execute(query, params)

    # Fetch and return updated config
    results = await repo_query("SELECT * FROM smtp_config WHERE id = 'default'")
    config = results[0]

    return SMTPConfigResponse(
        id=config["id"],
        smtp_host=config["smtp_host"],
        smtp_port=config["smtp_port"],
        smtp_username=config["smtp_username"],
        smtp_from_email=config["smtp_from_email"],
        smtp_from_name=config.get("smtp_from_name"),
        smtp_use_tls=bool(config["smtp_use_tls"]),
        smtp_use_ssl=bool(config["smtp_use_ssl"]),
        is_active=bool(config["is_active"]),
        created=config["created"],
        updated=config["updated"],
    )


@router.delete("/config", status_code=status.HTTP_204_NO_CONTENT)
async def delete_smtp_config():
    """Delete SMTP configuration"""
    query = "DELETE FROM smtp_config WHERE id = 'default'"
    await repo_execute(query)


@router.post("/test")
async def test_smtp_config(test_request: SMTPTestRequest):
    """Test SMTP configuration by sending a test email"""
    config = await SMTPService.get_config()

    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="SMTP not configured"
        )

    subject = "Test Email from Open Notebook"
    body = f"""
    <html>
    <body style="font-family: Arial, sans-serif; padding: 20px;">
        <h2>SMTP Configuration Test</h2>
        <p>This is a test email to verify your SMTP configuration.</p>
        <p>If you received this email, your SMTP settings are working correctly!</p>
        <hr>
        <p style="color: #666; font-size: 12px;">Sent from Open Notebook</p>
    </body>
    </html>
    """

    success = await SMTPService.send_email(
        to_email=test_request.test_email,
        subject=subject,
        body=body,
        is_html=True
    )

    if success:
        return {"message": f"Test email sent to {test_request.test_email}"}
    else:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send test email. Check your SMTP settings."
        )
