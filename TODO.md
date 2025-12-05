# TODO: Debug Flask-Mail SMTP Issue

## Completed Tasks
- [x] Analyzed app.py and identified MAIL_USE_TLS hardcoded to False, preventing Gmail SMTP connection
- [x] Updated mail configuration to use proper Gmail defaults (smtp.gmail.com, port 587, TLS enabled)
- [x] Added MAIL_USE_SSL = False explicitly
- [x] Set default sender to cmpquery@gmail.com
- [x] Added debug print statements to send_guest_response_email function for troubleshooting

## Next Steps
- [ ] Set environment variables: MAIL_USERNAME=email-cmpquery@gmail.com, MAIL_PASSWORD=16-digit-app-password, MAIL_USE_TLS=True
- [ ] Test email sending by visiting /test-smtp route in browser
- [ ] Submit a guest query and respond as admin to verify email delivery
- [ ] Check console output and app.log for debug messages
- [ ] If emails still fail, check Gmail account settings for "Less secure app access" or ensure app password is correct
- [ ] Remove debug print statements once issue is resolved
