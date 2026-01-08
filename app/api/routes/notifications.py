"""
API routes for email notifications and preferences.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_async_session
from app.models.user_preference import UserPreference

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/unsubscribe/{token}", response_class=HTMLResponse)
async def unsubscribe(
    token: str,
    db: AsyncSession = Depends(get_async_session),
) -> HTMLResponse:
    """
    Unsubscribe from all email notifications using unsubscribe token.

    Args:
        token: Unique unsubscribe token
        db: Database session

    Returns:
        HTML page confirming unsubscription
    """
    try:
        # Find user by unsubscribe token
        query = select(UserPreference).where(UserPreference.unsubscribe_token == token)
        result = await db.execute(query)
        user_pref = result.scalar_one_or_none()

        if not user_pref:
            logger.warning(f"Invalid unsubscribe token: {token}")
            return HTMLResponse(
                content="""
                <html>
                    <head>
                        <title>Invalid Unsubscribe Link</title>
                        <style>
                            body { font-family: Arial, sans-serif; max-width: 600px; margin: 50px auto; padding: 20px; }
                            .error { color: #d32f2f; }
                        </style>
                    </head>
                    <body>
                        <h1 class="error">Invalid Unsubscribe Link</h1>
                        <p>The unsubscribe link is invalid or has expired.</p>
                        <p>If you continue to receive unwanted emails, please contact support.</p>
                    </body>
                </html>
                """,
                status_code=status.HTTP_404_NOT_FOUND,
            )

        # Disable all notifications
        user_pref.enable_notifications = False
        user_pref.enable_daily_digest = False
        user_pref.enable_instant_alerts = False
        user_pref.enable_parent_escape_digest = False

        await db.commit()

        logger.info(
            f"User {user_pref.id} (email: {user_pref.email}) unsubscribed from all notifications"
        )

        return HTMLResponse(
            content=f"""
            <html>
                <head>
                    <title>Successfully Unsubscribed</title>
                    <style>
                        body {{ font-family: Arial, sans-serif; max-width: 600px; margin: 50px auto; padding: 20px; }}
                        .success {{ color: #388e3c; }}
                        .info {{ background-color: #e3f2fd; padding: 15px; border-radius: 5px; margin: 20px 0; }}
                    </style>
                </head>
                <body>
                    <h1 class="success">Successfully Unsubscribed</h1>
                    <p>You have been unsubscribed from all email notifications for <strong>{user_pref.email}</strong>.</p>
                    <div class="info">
                        <h3>What's been disabled:</h3>
                        <ul>
                            <li>Daily deal digest emails</li>
                            <li>Instant exceptional deal alerts</li>
                            <li>Parent escape recommendations</li>
                        </ul>
                    </div>
                    <p>You will no longer receive any emails from SmartFamilyTravelScout.</p>
                    <p><small>If you change your mind, you can re-enable notifications in your account preferences.</small></p>
                </body>
            </html>
            """,
            status_code=status.HTTP_200_OK,
        )

    except Exception as e:
        logger.error(f"Error processing unsubscribe request: {e}", exc_info=True)
        return HTMLResponse(
            content="""
            <html>
                <head>
                    <title>Error</title>
                    <style>
                        body { font-family: Arial, sans-serif; max-width: 600px; margin: 50px auto; padding: 20px; }
                        .error { color: #d32f2f; }
                    </style>
                </head>
                <body>
                    <h1 class="error">Error Processing Request</h1>
                    <p>An error occurred while processing your unsubscribe request.</p>
                    <p>Please try again later or contact support.</p>
                </body>
            </html>
            """,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@router.get("/unsubscribe/{token}/preferences", response_class=HTMLResponse)
async def unsubscribe_preferences(
    token: str,
    db: AsyncSession = Depends(get_async_session),
) -> HTMLResponse:
    """
    Show unsubscribe preferences page for fine-grained control.

    Args:
        token: Unique unsubscribe token
        db: Database session

    Returns:
        HTML page with preference options
    """
    try:
        # Find user by unsubscribe token
        query = select(UserPreference).where(UserPreference.unsubscribe_token == token)
        result = await db.execute(query)
        user_pref = result.scalar_one_or_none()

        if not user_pref:
            logger.warning(f"Invalid unsubscribe token: {token}")
            return HTMLResponse(
                content="""
                <html>
                    <head>
                        <title>Invalid Link</title>
                        <style>
                            body { font-family: Arial, sans-serif; max-width: 600px; margin: 50px auto; padding: 20px; }
                            .error { color: #d32f2f; }
                        </style>
                    </head>
                    <body>
                        <h1 class="error">Invalid Link</h1>
                        <p>The link is invalid or has expired.</p>
                    </body>
                </html>
                """,
                status_code=status.HTTP_404_NOT_FOUND,
            )

        # Generate preference management page
        daily_checked = "checked" if user_pref.enable_daily_digest else ""
        instant_checked = "checked" if user_pref.enable_instant_alerts else ""
        parent_checked = "checked" if user_pref.enable_parent_escape_digest else ""

        return HTMLResponse(
            content=f"""
            <html>
                <head>
                    <title>Email Preferences</title>
                    <style>
                        body {{ font-family: Arial, sans-serif; max-width: 600px; margin: 50px auto; padding: 20px; }}
                        h1 {{ color: #1976d2; }}
                        .preference {{ margin: 15px 0; padding: 10px; border: 1px solid #e0e0e0; border-radius: 5px; }}
                        .preference label {{ font-weight: bold; }}
                        .preference p {{ margin: 5px 0 0 25px; color: #666; font-size: 0.9em; }}
                        button {{ background-color: #1976d2; color: white; padding: 10px 20px; border: none; border-radius: 5px; cursor: pointer; font-size: 1em; }}
                        button:hover {{ background-color: #1565c0; }}
                    </style>
                </head>
                <body>
                    <h1>Email Notification Preferences</h1>
                    <p>Manage your email notification settings for <strong>{user_pref.email}</strong></p>

                    <form method="post" action="/notifications/unsubscribe/{token}/update">
                        <div class="preference">
                            <label>
                                <input type="checkbox" name="enable_daily_digest" {daily_checked}>
                                Daily Deal Digest
                            </label>
                            <p>Receive a daily email with the top travel deals</p>
                        </div>

                        <div class="preference">
                            <label>
                                <input type="checkbox" name="enable_instant_alerts" {instant_checked}>
                                Instant Exceptional Deal Alerts
                            </label>
                            <p>Get notified immediately when we find an exceptional deal (score 85+)</p>
                        </div>

                        <div class="preference">
                            <label>
                                <input type="checkbox" name="enable_parent_escape_digest" {parent_checked}>
                                Parent Escape Recommendations
                            </label>
                            <p>Weekly digest of romantic getaways for parents</p>
                        </div>

                        <button type="submit">Save Preferences</button>
                    </form>

                    <p style="margin-top: 30px; font-size: 0.9em; color: #666;">
                        <a href="/notifications/unsubscribe/{token}">Unsubscribe from all emails</a>
                    </p>
                </body>
            </html>
            """,
            status_code=status.HTTP_200_OK,
        )

    except Exception as e:
        logger.error(f"Error showing preferences: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error loading preferences",
        )
