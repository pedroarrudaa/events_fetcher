# Events Dashboard Setup Guide

This project consists of a FastAPI backend and React frontend for displaying and filtering hackathons and conferences from your database.

## Project Structure

```
/
├── backend.py              # FastAPI server
├── requirements.txt        # Python dependencies
├── database_utils.py       # Database utilities (existing)
├── frontend/               # React frontend
│   ├── package.json
│   ├── tailwind.config.js
│   ├── postcss.config.js
│   ├── public/
│   │   └── index.html
│   └── src/
│       ├── index.js
│       ├── index.css
│       ├── App.js
│       └── components/
│           └── EventsPage.jsx
```

## Backend Setup

### 1. Install Python Dependencies

```bash
pip install -r requirements.txt
```

### 2. Environment Variables

Make sure you have a `.env` file with your database configuration:

```bash
# .env
DATABASE_URL=postgresql://username:password@host:port/database
```

### 3. Run the FastAPI Server

```bash
# Development mode with auto-reload
python backend.py

# Or using uvicorn directly
uvicorn backend:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at:
- Main API: http://localhost:8000
- Interactive docs: http://localhost:8000/docs
- Health check: http://localhost:8000/health

### API Endpoints

- `GET /events` - Get all events with optional filters
  - Query parameters:
    - `type_filter`: "hackathon", "conference", or "all"
    - `location_filter`: location string or "all"
    - `status_filter`: "validated", "enriched", "filtered", or "all"
    - `limit`: number of results to return

- `GET /health` - Health check with database status
- `GET /` - Basic API info

## Frontend Setup

### 1. Navigate to Frontend Directory

```bash
cd frontend
```

### 2. Install Node.js Dependencies

```bash
npm install
```

### 3. Start the Development Server

```bash
npm start
```

The React app will be available at http://localhost:3000

### 4. Build for Production

```bash
npm run build
```

## Features

### Backend Features
- **FastAPI** with automatic API documentation
- **CORS support** for frontend integration
- **Database integration** with fallback to mock data
- **Unified event model** combining hackathons and conferences
- **Filtering support** by type, location, and status
- **Error handling** and health checks

### Frontend Features
- **Responsive design** using Tailwind CSS
- **Real-time filtering** by type, location, and status
- **Loading states** with animated spinners
- **Error handling** with user-friendly messages
- **Clickable URLs** opening in new tabs
- **Status badges** with color coding
- **Mobile-responsive table** with horizontal scrolling
- **Refresh functionality** to reload data

## Usage

1. **Start the backend** on port 8000
2. **Start the frontend** on port 3000
3. **Open your browser** to http://localhost:3000
4. **Use the filters** to browse events:
   - Filter by type (All, Hackathon, Conference)
   - Filter by location (All, San Francisco, New York, Remote)
   - Filter by status (All, Validated, Enriched, Filtered)

## Data Model

The unified event model includes:
- `title`: Event name
- `type`: "hackathon" or "conference"  
- `location`: Event location
- `start_date`: Event start date
- `end_date`: Event end date
- `url`: Event website (clickable)
- `status`: Data quality status

## Status Meanings

- **Validated**: Basic event information verified
- **Enriched**: Complete information with all fields populated
- **Filtered**: Incomplete information, may need review

## Troubleshooting

### Backend Issues

1. **Database connection fails**: The backend will automatically fall back to mock data
2. **Port already in use**: Change the port in `backend.py` or kill the existing process
3. **Import errors**: Make sure all dependencies are installed with `pip install -r requirements.txt`

### Frontend Issues

1. **API connection fails**: Check that the backend is running on port 8000
2. **Styling issues**: Make sure Tailwind CSS is properly configured
3. **Build errors**: Clear `node_modules` and reinstall: `rm -rf node_modules && npm install`

### CORS Issues

If you encounter CORS errors:
1. Make sure the backend CORS middleware includes your frontend URL
2. Check that both frontend and backend are running on the expected ports
3. Try using `127.0.0.1` instead of `localhost` if needed

## Development Notes

- The backend automatically handles both database connections and mock data fallback
- Frontend API URL is configurable in `EventsPage.jsx` (`API_BASE_URL` constant)
- All event data is normalized to a common format regardless of source table
- Responsive design works on mobile, tablet, and desktop
- Status determination is automatic based on data completeness

## Production Deployment

### Backend
- Use a production WSGI server like Gunicorn with Uvicorn workers
- Set up proper environment variables
- Configure database connection pooling
- Add authentication if needed

### Frontend
- Build with `npm run build`
- Serve static files with nginx or similar
- Update API_BASE_URL to production backend URL
- Configure proper CORS origins in backend

## Next Steps

Potential enhancements:
- Add sorting functionality to table columns
- Implement pagination for large datasets
- Add search functionality
- Include more detailed event information in modals
- Add event creation/editing capabilities
- Implement user authentication and favorites 