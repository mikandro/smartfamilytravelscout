# Email Notification System

Beautiful HTML email notifications for SmartFamilyTravelScout with support for multiple SMTP providers.

## Features

- **Multiple Email Types**:
  - Daily Digest: Top 5 family travel deals (score > 70)
  - Deal Alert: Immediate notifications for exceptional deals (score > 85)
  - Parent Escape Digest: Weekly romantic getaway roundup

- **Beautiful HTML Templates**:
  - Mobile-responsive design
  - Professional styling with gradients and cards
  - Tested in Gmail, Outlook, and Apple Mail

- **SMTP Provider Support**:
  - Gmail
  - SendGrid
  - Mailgun
  - Outlook/Office365
  - Amazon SES
  - Custom SMTP servers

- **Developer Features**:
  - Email preview generation
  - Test email sending
  - Error handling and retry logic
  - Jinja2 template system

## Configuration

### Environment Variables

Add these to your `.env` file:

```bash
# SMTP Configuration
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your_email@gmail.com
SMTP_PASSWORD=your_app_password
SMTP_FROM_EMAIL=noreply@smartfamilytravelscout.com
SMTP_FROM_NAME=SmartFamilyTravelScout
```

### Gmail Setup

1. Enable 2-factor authentication on your Google account
2. Generate an app-specific password:
   - Go to https://myaccount.google.com/apppasswords
   - Select 'Mail' and your device
   - Copy the generated 16-character password
3. Use this password for `SMTP_PASSWORD`

### SendGrid Setup

```bash
SMTP_HOST=smtp.sendgrid.net
SMTP_PORT=587
SMTP_USER=apikey
SMTP_PASSWORD=your_sendgrid_api_key
```

### Mailgun Setup

```bash
SMTP_HOST=smtp.mailgun.org  # or smtp.eu.mailgun.org for EU
SMTP_PORT=587
SMTP_USER=postmaster@your-domain.com
SMTP_PASSWORD=your_mailgun_smtp_password
```

## Usage

### Basic Usage

```python
from app.notifications import create_email_notifier
from app.models.trip_package import TripPackage

# Create email notifier
notifier = create_email_notifier(user_email="user@example.com")

# Send daily digest
deals = TripPackage.query.filter(TripPackage.ai_score > 70).limit(5).all()
await notifier.send_daily_digest(deals)

# Send deal alert for exceptional deal
exceptional_deal = TripPackage.query.filter(TripPackage.ai_score > 85).first()
await notifier.send_deal_alert(exceptional_deal)

# Send parent escape digest
escapes = TripPackage.query.filter(TripPackage.package_type == "parent_escape").limit(5).all()
await notifier.send_parent_escape_digest(escapes)
```

### Preview Emails (HTML Generation)

Generate HTML previews without sending:

```python
from app.notifications import create_email_notifier

notifier = create_email_notifier()

# Preview daily digest
html = notifier.preview_daily_digest(deals)
with open("preview.html", "w") as f:
    f.write(html)
```

### CLI Preview Tool

Generate HTML previews for all templates:

```bash
# Preview all templates
python -m app.notifications.email_preview preview all

# Preview specific template
python -m app.notifications.email_preview preview daily
python -m app.notifications.email_preview preview alert
python -m app.notifications.email_preview preview escape
```

This creates preview files in `email_previews/` directory.

### Send Test Emails

```bash
# Send test daily digest
python -m app.notifications.email_preview send daily your@email.com

# Send test deal alert
python -m app.notifications.email_preview send alert your@email.com

# Send test parent escape digest
python -m app.notifications.email_preview send escape your@email.com
```

## Email Templates

Templates are located in `app/notifications/templates/`:

- `daily_digest.html` - Daily deals summary
- `deal_alert.html` - Urgent exceptional deal notification
- `parent_escape.html` - Weekly romantic getaway digest

### Template Variables

**Daily Digest:**
```python
{
    'deals': List[TripPackage],
    'date': date.today(),
    'total_deals': int,
    'summary': str
}
```

**Deal Alert:**
```python
{
    'deal': TripPackage,
    'date': date.today()
}
```

**Parent Escape:**
```python
{
    'getaways': List[TripPackage],
    'date': date.today(),
    'total_getaways': int,
    'summary': str
}
```

## Custom Filters

Templates have access to custom Jinja2 filters:

- `{{ value | round(decimals) }}` - Round numbers
- `{{ date | format_date }}` - Format dates (e.g., "January 15, 2025")
- `{{ price | format_price }}` - Format prices (e.g., "€1,234.56")

## Error Handling

The email system includes comprehensive error handling:

```python
# Returns True/False based on success
success = await notifier.send_daily_digest(deals)

if not success:
    logger.error("Failed to send email - check SMTP configuration")
```

Common errors:
- `SMTPAuthenticationError`: Invalid credentials
- `SMTPException`: SMTP server error
- `TimeoutError`: Connection timeout

## Integration with Celery

Schedule automated emails using Celery:

```python
from app.tasks.celery_app import celery_app
from app.notifications import create_email_notifier

@celery_app.task
def send_daily_digest_task():
    """Send daily digest to all users."""
    from app.models.trip_package import TripPackage
    from app.database import get_db

    db = next(get_db())

    # Get top deals
    deals = db.query(TripPackage).filter(
        TripPackage.ai_score > 70,
        TripPackage.notified == False
    ).order_by(TripPackage.ai_score.desc()).limit(5).all()

    if deals:
        notifier = create_email_notifier(user_email="user@example.com")
        success = await notifier.send_daily_digest(deals)

        if success:
            # Mark as notified
            for deal in deals:
                deal.notified = True
            db.commit()

# Schedule in celerybeat
from celery.schedules import crontab

celery_app.conf.beat_schedule = {
    'send-daily-digest': {
        'task': 'app.tasks.scheduled_tasks.send_daily_digest_task',
        'schedule': crontab(hour=8, minute=0),  # 8 AM daily
    },
}
```

## Unsubscribe Handling

Email templates include unsubscribe links:

```
https://smartfamilytravelscout.com/unsubscribe
```

Implement this endpoint to handle unsubscribe requests.

## Testing Checklist

- [ ] HTML renders correctly in Gmail
- [ ] HTML renders correctly in Outlook
- [ ] HTML renders correctly on mobile devices
- [ ] Links work properly
- [ ] Images display (if used)
- [ ] Unsubscribe link works
- [ ] SMTP authentication succeeds
- [ ] Email sends successfully
- [ ] Error handling works properly

## Performance

- Templates are loaded once and cached
- Connection pooling for SMTP (reusable connections)
- Timeout protection (30 seconds default)
- Async support for non-blocking operations

## Security

- Never commit SMTP credentials to version control
- Use app-specific passwords for Gmail
- Use environment variables for all secrets
- Validate email addresses before sending
- Rate limit email sending to prevent abuse

## Troubleshooting

**Email not sending:**
1. Check SMTP credentials in `.env`
2. Verify SMTP server and port
3. Check firewall/network settings
4. Review logs for specific errors

**Template not found:**
1. Verify templates directory exists: `app/notifications/templates/`
2. Check template file names match exactly
3. Ensure file permissions allow reading

**HTML not rendering properly:**
1. Test in multiple email clients
2. Validate HTML structure
3. Check inline CSS (some clients strip `<style>` tags)
4. Use tables for layout (better email client support)

## Development

Run tests:
```bash
pytest app/notifications/tests/
```

Lint templates:
```bash
# Check HTML validity
tidy -q -e app/notifications/templates/*.html
```

## License

Part of SmartFamilyTravelScout project.
