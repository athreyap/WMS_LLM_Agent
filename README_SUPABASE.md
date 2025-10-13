# WMS Portfolio Analytics - Supabase Version

A modern portfolio analytics application built with Streamlit and Supabase for cloud-based data storage and user management.

## 🚀 Features

- **Cloud-based Storage**: Uses Supabase for scalable, secure data storage
- **User Authentication**: Secure login/registration system
- **Portfolio Analytics**: Comprehensive investment portfolio analysis
- **Interactive Charts**: Beautiful visualizations with Plotly
- **File Upload**: Support for CSV transaction files
- **Real-time Data**: Live portfolio updates and calculations

## 📋 Prerequisites

- Python 3.8 or higher
- Supabase account (free tier available)
- pip package manager

## 🛠️ Installation

### 1. Clone the Repository

```bash
git clone <repository-url>
cd WMS-LLM
```

### 2. Install Dependencies

```bash
pip install -r requirements_supabase.txt
```

### 3. Setup Supabase

#### Option A: Automated Setup
```bash
python setup_supabase.py
```

#### Option B: Manual Setup

1. **Create a Supabase Project**:
   - Go to [supabase.com](https://supabase.com)
   - Sign up and create a new project
   - Note your project URL and anon key

2. **Create Environment File**:
   Create a `.env` file in the project root:
   ```env
   SUPABASE_URL=your-supabase-project-url
   SUPABASE_KEY=your-supabase-anon-key
   ```

3. **Create Database Tables**:
   Run the following SQL in your Supabase SQL Editor:

   ```sql
   -- Create investment_files table
   CREATE TABLE investment_files (
       id BIGSERIAL PRIMARY KEY,
       filename TEXT NOT NULL,
       original_filename TEXT NOT NULL,
       file_hash TEXT UNIQUE NOT NULL,
       customer_name TEXT,
       customer_id TEXT,
       customer_email TEXT,
       customer_phone TEXT,
       file_path TEXT NOT NULL,
       upload_date TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
       file_size INTEGER,
       status TEXT DEFAULT 'active'
   );

   -- Create investment_transactions table
   CREATE TABLE investment_transactions (
       id BIGSERIAL PRIMARY KEY,
       file_id INTEGER REFERENCES investment_files(id),
       user_id INTEGER,
       channel TEXT,
       stock_name TEXT,
       ticker TEXT,
       quantity DECIMAL,
       price DECIMAL,
       transaction_type TEXT,
       date TEXT,
       amount DECIMAL,
       created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
   );

   -- Create user_login table
   CREATE TABLE user_login (
       id BIGSERIAL PRIMARY KEY,
       username TEXT UNIQUE,
       email TEXT UNIQUE,
       password_hash TEXT,
       password_salt TEXT,
       role TEXT DEFAULT 'user',
       folder_path TEXT,
       created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
       last_login TIMESTAMP WITH TIME ZONE,
       is_active BOOLEAN DEFAULT TRUE,
       failed_attempts INTEGER DEFAULT 0,
       locked_until TIMESTAMP WITH TIME ZONE
   );
   ```

### 4. Run the Application

```bash
streamlit run simple_app_supabase.py
```

The application will open in your browser at `http://localhost:8501`

## 📊 Usage

### 1. Registration/Login
- First-time users need to register with username, email, and password
- Existing users can login with their credentials
- Optional folder path can be configured during registration

### 2. Upload Data
- Upload CSV files containing investment transactions
- Supported columns: date, transaction_type, quantity, price, stock_name, ticker, channel
- Files are automatically processed and stored in Supabase

### 3. View Analytics
- **Portfolio Summary**: Overview of total investments, current value, and P&L
- **Channel Distribution**: Pie chart showing allocation across different channels
- **Transaction Types**: Bar chart of buy/sell transactions
- **Data Table**: Detailed view of all transactions

## 📁 File Structure

```
WMS-LLM/
├── simple_app_supabase.py          # Main Streamlit application
├── database_config_supabase.py     # Supabase database configuration
├── setup_supabase.py              # Setup script
├── requirements_supabase.txt       # Python dependencies
├── README_SUPABASE.md             # This file
└── .env                           # Environment variables (create this)
```

## 🔧 Configuration

### Environment Variables

Create a `.env` file with the following variables:

```env
SUPABASE_URL=your-supabase-project-url
SUPABASE_KEY=your-supabase-anon-key
```

### CSV File Format

Your CSV files should contain the following columns:

| Column | Description | Required |
|--------|-------------|----------|
| date | Transaction date (YYYY-MM-DD) | Yes |
| transaction_type | Buy or Sell | Yes |
| quantity | Number of shares/units | Yes |
| price | Price per share/unit | Yes |
| stock_name | Name of the stock/fund | No |
| ticker | Stock/fund symbol | No |
| channel | Investment channel | No |

## 🔒 Security Features

- **Password Hashing**: Passwords are hashed with salt using SHA-256
- **User Authentication**: Secure login system with session management
- **Data Isolation**: Users can only access their own data
- **Input Validation**: All user inputs are validated and sanitized

## 🚀 Deployment

### Local Development
```bash
streamlit run simple_app_supabase.py
```

### Cloud Deployment

#### Streamlit Cloud
1. Push your code to GitHub
2. Connect your repository to Streamlit Cloud
3. Add environment variables in Streamlit Cloud settings
4. Deploy

#### Heroku
1. Create a `Procfile`:
   ```
   web: streamlit run simple_app_supabase.py --server.port=$PORT --server.address=0.0.0.0
   ```
2. Add environment variables in Heroku dashboard
3. Deploy using Heroku CLI or GitHub integration

## 🔧 Troubleshooting

### Common Issues

1. **Supabase Connection Error**:
   - Verify your Supabase URL and key in `.env` file
   - Check if your Supabase project is active
   - Ensure tables are created in Supabase

2. **Import Errors**:
   - Install all dependencies: `pip install -r requirements_supabase.txt`
   - Check Python version (3.8+ required)

3. **Data Not Loading**:
   - Verify CSV file format
   - Check required columns are present
   - Ensure file encoding is UTF-8

### Getting Help

- Check the console output for error messages
- Verify Supabase dashboard for data storage
- Test database connection using `setup_supabase.py`

## 📈 Performance Optimization

The application includes several optimizations:

- **Caching**: Streamlit caching for improved performance
- **Batch Processing**: Efficient data processing for large files
- **Memory Management**: Optimized data handling for large datasets
- **Connection Pooling**: Efficient database connections

## 🔄 Migration from PostgreSQL

If you're migrating from the PostgreSQL version:

1. Export your data from PostgreSQL
2. Convert to CSV format if needed
3. Upload to the Supabase version
4. Update your environment variables

## 📝 License

This project is licensed under the MIT License.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## 📞 Support

For support and questions:
- Create an issue in the repository
- Check the troubleshooting section
- Review Supabase documentation

---

**Note**: This is the Supabase version of the WMS Portfolio Analytics application. For the PostgreSQL version, see the main README file.
