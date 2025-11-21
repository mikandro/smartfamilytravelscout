# Security Policy

## Supported Versions

The following versions of SmartFamilyTravelScout are currently being supported with security updates:

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |
| < 0.1   | :x:                |

## Reporting a Vulnerability

We take the security of SmartFamilyTravelScout seriously. If you discover a security vulnerability, please follow the responsible disclosure process outlined below.

### How to Report

**DO NOT** create a public GitHub issue for security vulnerabilities. Instead:

1. **Email us directly** at the repository owner's email (check the repository for contact information)
2. **Alternative**: Use GitHub's private security advisory feature at `https://github.com/mikandro/smartfamilytravelscout/security/advisories/new`
3. Include the following information:
   - Description of the vulnerability
   - Steps to reproduce the issue
   - Potential impact
   - Any suggested fixes (optional)

### Response Timeline

- **Initial Response**: We aim to respond within 48 hours of receiving your report
- **Status Updates**: You will receive updates on the progress every 5-7 days
- **Resolution**: We will work to resolve critical vulnerabilities within 30 days

### What to Expect

After you submit a vulnerability report:

1. **Acknowledgment**: We will acknowledge receipt of your report within 48 hours
2. **Severity Assessment**: We will evaluate the severity and impact of the vulnerability
3. **Fix Development**: Our team will develop and test a fix
4. **Patch Release**: We will release a security patch as soon as possible
5. **Public Disclosure**: After the patch is released, we will publicly disclose the vulnerability (coordinating with you on the timeline)
6. **Credit**: We will credit you in the security advisory unless you prefer to remain anonymous

## Security Best Practices for Deployment

If you're deploying SmartFamilyTravelScout, follow these security guidelines:

### 1. Credentials and API Keys

- **Never commit** `.env` files or secrets to version control
- Use environment variables or secure secret management systems (AWS Secrets Manager, HashiCorp Vault, etc.)
- Rotate API keys regularly, especially:
  - `ANTHROPIC_API_KEY`
  - `KIWI_API_KEY`
  - `EVENTBRITE_API_KEY`
  - `SECRET_KEY` (for session management)

### 2. HTTPS Enforcement

- Always use HTTPS in production
- Configure your reverse proxy (nginx, Traefik, etc.) to redirect HTTP to HTTPS
- Use valid TLS certificates (Let's Encrypt, etc.)

### 3. Database Security

- Use strong passwords for PostgreSQL
- **Never expose** the database port (5432) to the public internet
- Use connection pooling with appropriate limits
- Enable PostgreSQL SSL connections in production
- Regularly backup your database with encrypted backups

### 4. Dependency Management

- Regularly update dependencies: `poetry update`
- Monitor for security advisories: `poetry show --outdated`
- Use `pip-audit` or similar tools to scan for known vulnerabilities
- Pin dependency versions in production

### 5. Data Encryption

- Encrypt sensitive data at rest (database encryption)
- Use encrypted connections for all external APIs
- Ensure Redis uses password authentication
- Consider encrypting user email addresses in the database

### 6. Network Security

- Use Docker networks to isolate services
- Configure firewall rules to restrict access
- Use fail2ban or similar tools to prevent brute-force attacks
- Implement rate limiting on API endpoints

### 7. Logging and Monitoring

- Enable comprehensive logging (application, database, web server)
- Monitor for suspicious activity
- Set up alerts for failed authentication attempts
- Regularly review logs for security incidents
- **DO NOT log** sensitive data (passwords, full API keys, credit card numbers)

### 8. Secrets Management

- Use Docker secrets or Kubernetes secrets in orchestrated environments
- Avoid storing secrets in `docker-compose.yml`
- Use read-only mounts for configuration files
- Implement proper file permissions (0600 for sensitive files)

## Known Security Considerations

We are aware of the following security considerations in the current version:

### 1. Environment Variable Handling

**Status**: ⚠️ Under Review

- The project currently uses `.env` files for local development
- **Risk**: Accidental commits of `.env` files could expose secrets
- **Mitigation**:
  - `.env` is in `.gitignore`
  - Use `.env.example` as a template
  - Document proper secret management in production
- **Future**: Consider implementing a secrets validation tool

### 2. Database Credentials in docker-compose.yml

**Status**: ⚠️ Under Review

- `docker-compose.yml` contains default database credentials
- **Risk**: Weak default passwords if used in production
- **Mitigation**:
  - Default credentials are only for local development
  - Documentation emphasizes using environment-specific configuration
  - Production deployments should use secure credential management
- **Future**: Remove default credentials and require explicit configuration

### 3. API Rate Limiting

**Status**: ⚠️ Planned for v0.2.0

- Current API endpoints lack rate limiting
- **Risk**: Potential for abuse or DoS attacks
- **Mitigation**:
  - Deploy behind a reverse proxy with rate limiting (nginx, Traefik)
  - Use cloud provider rate limiting (AWS WAF, Cloudflare, etc.)
- **Future**: Implement application-level rate limiting using Redis

### 4. Web Scraping Considerations

**Status**: ℹ️ By Design

- The application uses web scraping which may violate terms of service
- **Risk**: Legal concerns, IP blocking, ethical considerations
- **Mitigation**:
  - Respect robots.txt
  - Implement polite scraping with delays
  - Use official APIs where available (Kiwi.com, Eventbrite)
  - Users are responsible for compliance with ToS
- **Note**: This is a personal/educational project

### 5. AI API Costs

**Status**: ℹ️ Monitoring Required

- Anthropic Claude API usage can incur significant costs
- **Risk**: Unexpected API bills from excessive usage
- **Mitigation**:
  - Cost tracking implemented in `api_cost` table
  - Set up billing alerts in Anthropic dashboard
  - Implement request throttling for AI features
  - Monitor token usage regularly

### 6. User Input Validation

**Status**: ✅ Implemented

- FastAPI Pydantic models provide input validation
- SQL injection protection via SQLAlchemy ORM
- XSS protection through Jinja2 auto-escaping
- **Continue**: Regular security audits of input handling

## Security Updates

Security updates will be released as patch versions (e.g., 0.1.1) and announced via:

- GitHub Security Advisories
- Release notes
- Repository README

## Contact

For security concerns that are not vulnerabilities (questions, best practices, etc.), please:

- Open a regular GitHub issue with the "security" label
- Check existing documentation in CLAUDE.md and README.md

## Acknowledgments

We appreciate the security research community's efforts in responsibly disclosing vulnerabilities. Contributors who report valid security issues will be acknowledged (unless they prefer to remain anonymous) in:

- Security advisories
- CHANGELOG.md
- Project documentation

Thank you for helping keep SmartFamilyTravelScout and its users safe!
