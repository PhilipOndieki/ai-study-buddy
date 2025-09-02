this is the initial readme 
# AI Study Buddy Backend

Flask-based backend API for the AI Study Buddy flashcard generator.

## Features

- **RESTful API**: Clean endpoints for flashcard generation and management
- **MySQL Integration**: Persistent data storage with SQLAlchemy ORM
- **AI Question Generation**: Intelligent flashcard creation from study notes
- **User Management**: Session-based authentication and user tracking
- **Premium Features**: Subscription management with IntaSend integration
- **Study Analytics**: Progress tracking and performance metrics

## Quick Start

### Prerequisites

- Python 3.8+
- MySQL 8.0+
- pip (Python package manager)

### Installation

1. **Install dependencies:**
   ```bash
   cd backend
   pip install -r requirements.txt
   ```

2. **Set up MySQL database:**
   ```bash
   # Login to MySQL as root
   mysql -u root -p
   
   # Run the setup script
   source database_setup.sql
   ```

3. **Configure environment variables:**
   ```bash
   cp .env.example .env
   # Edit .env with your database credentials and API keys
   ```

4. **Run the application:**
   ```bash
   python run.py
   ```

The backend will start on `http://127.0.0.1:5000`

## Database Configuration

### Connection String Format
```
mysql+pymysql://username:password@host:port/database_name
```

### Example Configurations

**Local Development:**
```
DATABASE_URL=mysql+pymysql://ai_study_user:secure_password_here@localhost/ai_study_buddy_dev
```

**Production:**
```
DATABASE_URL=mysql+pymysql://username:password@your-mysql-host.com:3306/ai_study_buddy
```

## API Endpoints

### Core Endpoints

- `GET /api/health` - Health check and system status
- `POST /api/users` - Create user account
- `POST /api/generate-flashcards` - Generate flashcards from notes
- `GET /api/decks` - Get user's flashcard decks
- `GET /api/decks/{id}` - Get specific deck with cards
- `PUT /api/decks/{id}` - Update deck information

### Study Session Endpoints

- `POST /api/study-session` - Start new study session
- `POST /api/study-session/{id}/complete` - Complete study session
- `POST /api/cards/{id}/study` - Record card study attempt

### Premium Endpoints

- `POST /api/premium/upgrade` - Upgrade to premium subscription
- `GET /api/user/stats` - Get user statistics and progress

## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `DATABASE_URL` | MySQL connection string | Yes |
| `SECRET_KEY` | Flask session secret key | Yes |
| `OPENROUTER_API_KEY` | AI model API token | Optional |
| `PAYSTACK_PUBLIC_KEY` | Payment gateway public key | Optional |
| `PAYSTACK_SECRET_KEY` | Payment gateway secret key | Optional |

## Development

### Running in Development Mode

```bash
export FLASK_ENV=development
export FLASK_DEBUG=True
python run.py
```

### Database Migrations

The application automatically creates tables on first run. For schema changes:

1. Update models in `app.py`
2. Restart the application
3. Tables will be updated automatically

### Testing the API

```bash
# Health check
curl http://127.0.0.1:5000/api/health

# Generate flashcards
curl -X POST http://127.0.0.1:5000/api/generate-flashcards \
  -H "Content-Type: application/json" \
  -d '{"notes": "Your study notes here..."}'
```

## Production Deployment

### Using Gunicorn

```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 run:app
```

### Environment Setup

1. Set `FLASK_ENV=production`
2. Use strong `SECRET_KEY`
3. Configure production MySQL database
4. Set up SSL/TLS certificates
5. Configure reverse proxy (nginx recommended)

## Security Considerations

- **Database Security**: Use dedicated database user with minimal privileges
- **Session Management**: Secure session cookies with HTTPS in production
- **Input Validation**: All user inputs are validated and sanitized
- **Rate Limiting**: Consider implementing rate limiting for API endpoints
- **CORS**: Configured for specific frontend origins

## Monitoring

- **Logging**: Comprehensive logging with Python's logging module
- **Health Checks**: `/api/health` endpoint for monitoring
- **Error Handling**: Graceful error responses with proper HTTP status codes

## Integration Points

### Frontend Integration
The backend is designed to work seamlessly with the existing vanilla JavaScript frontend. The API service (`js/api.js`) handles all communication.

### AI Integration
Ready for OPENROUTER_API_KEY integration. Set `OPENROUTER_API_KEY` environment variable to enable real AI question generation.

### Payment Integration
Paystack payment gateway integration ready. Configure Paystack credentials in environment variables.

## Troubleshooting

### Common Issues

1. **Database Connection Failed**
   - Check MySQL is running
   - Verify credentials in DATABASE_URL
   - Ensure database exists

2. **CORS Errors**
   - Check frontend URL in CORS configuration
   - Verify credentials are included in requests

3. **Session Issues**
   - Check SECRET_KEY is set
   - Verify cookies are enabled in browser

### Logs

Check application logs for detailed error information:
```bash
tail -f app.log
```

add to run the frontend you go to index.html and run the server 

add the contributors 
Philip Barongo Ondieki  
gmail: philipbarongo30@gmail.com

Afolabi Samuel
gmail: samuel.afolabi1@miva.edu.ng

Muhammad Adams
muhadam2011@gmail.com
