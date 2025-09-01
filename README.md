# WMS-LLM: Wealth Management System with LLM Integration

A comprehensive portfolio analytics application built with Streamlit, featuring multi-user support, real-time stock data, and intelligent file processing.

## Features

- **Multi-User Support**: Secure login system with user-specific data isolation
- **Real-Time Portfolio Analytics**: Live stock prices, P&L calculations, and performance metrics
- **Intelligent File Processing**: Automatic CSV file monitoring and processing
- **Advanced Filtering**: Cascading filters for Channel, Sector, and Stock analysis
- **Performance Optimization**: Smart caching and bulk data operations
- **Cloud-Ready**: Optimized for Streamlit Cloud deployment

## Quick Start

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/WMS-LLM.git
   cd WMS-LLM
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements_supabase.txt
   ```

3. **Set up environment variables**
   ```bash
   # Create .env file or set environment variables
   DATABASE_URL=your_supabase_connection_string
   ```

4. **Run the application**
   ```bash
   streamlit run web_agent.py
   ```

## Deployment on Streamlit Cloud

1. **Fork this repository** to your GitHub account
2. **Connect to Streamlit Cloud** and deploy from your fork
3. **Add secrets** in Streamlit Cloud:
   - `DATABASE_URL`: Your Supabase PostgreSQL connection string
4. **Deploy** and enjoy!

## File Structure

```
WMS-LLM/
├── web_agent.py                 # Main Streamlit application
├── stock_data_agent.py          # Stock data management
├── user_file_reading_agent.py   # File processing agent
├── file_manager.py              # File utilities and price fetching
├── mf_price_fetcher.py          # Mutual fund price fetching
├── indstocks_api.py             # Indian stocks API integration
├── login_system.py              # User authentication
├── database_config_supabase.py  # Database configuration
├── requirements_supabase.txt    # Python dependencies
├── .gitignore                   # Git ignore rules
├── README.md                    # This file
└── investments/                 # Sample investment files
```

## Configuration

### Database Setup
The application uses Supabase PostgreSQL. Ensure your database has the following tables:
- `users`
- `investment_transactions`
- `investment_files`
- `stock_data`

### Environment Variables
- `DATABASE_URL`: Supabase PostgreSQL connection string

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details. 