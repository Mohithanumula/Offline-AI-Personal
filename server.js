const express = require('express');
const cors = require('cors');
const dotenv = require('dotenv');
const path = require('path');

dotenv.config();

const app = express();
const PORT = process.env.PORT || 3000;

// Middleware
app.use(cors());
app.use(express.json());
app.use(express.urlencoded({ extended: true }));

// Serve frontend files
app.use(express.static(path.join(__dirname, '../frontend')));

// Routes
const uploadRoute = require('./routes/upload');
const queryRoute = require('./routes/query');
const authRoute = require('./routes/auth');

app.use('/api/upload', uploadRoute);
app.use('/api/query', queryRoute);
app.use('/api/auth', authRoute);

// Image route
app.get('/api/images', async (req, res) => {
    try {
        const axios = require('axios');
        const keyword = req.query.keyword || 'image';
        const response = await axios.get(`http://localhost:8000/images?keyword=${encodeURIComponent(keyword)}`);
        res.json(response.data);
    } catch (error) {
        res.status(500).json({ success: false, error: error.message, images: [] });
    }
});

// Health check
app.get('/api/health', (req, res) => {
    res.json({ status: 'Server is running!', port: PORT });
});

// Default route → redirect to login
app.get('/', (req, res) => {
    res.sendFile(path.join(__dirname, '../frontend/login.html'));
});

// Start server
app.listen(PORT, () => {
    console.log(`✅ Server running on http://localhost:${PORT}`);
});
app.get('/api/stats', async (req, res) => {
    try {
        const axios = require('axios');
        const response = await axios.get('http://localhost:8000/stats');
        res.json(response.data);
    } catch (error) {
        res.status(500).json({ success: false, error: error.message });
    }
});

app.get('/api/analyse-image', async (req, res) => {
    try {
        const axios = require('axios');
        const { keyword, question } = req.query;
        const response = await axios.get(
            `http://localhost:8000/analyse-image?keyword=${encodeURIComponent(keyword)}&question=${encodeURIComponent(question)}`
        );
        res.json(response.data);
    } catch (error) {
        res.status(500).json({ success: false, answer: error.message });
    }
});