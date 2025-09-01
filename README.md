# WMS-LLM Portfolio Analyzer

A comprehensive investment portfolio analysis tool built with Streamlit, featuring secure user authentication, automated file processing, and real-time portfolio tracking.

## 🚀 Key Features

- **🔐 Secure User Authentication**: Role-based access control with password hashing and account lockout protection
- **📁 Simplified File Management**: Automatic processing of CSV files from user-specific folders
- **📊 Real-time Portfolio Analysis**: Live price fetching using INDmoney API with yfinance fallback
- **📈 Interactive Visualizations**: Charts and graphs for portfolio performance analysis
- **🗄️ PostgreSQL Database**: Robust data storage with user-specific transaction management
- **🔄 Automatic File Archiving**: Processed files are automatically moved to archive folders

## 📋 Requirements

- Python 3.8+
- PostgreSQL database
- Required Python packages (see `requirements.txt`)

## 🛠️ Installation

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd WMS-LLM
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up PostgreSQL database**:
   ```bash
   python create_database.py
   ```

4. **Create admin user**:
   ```bash
   python create_admin_user.py
   ```

## 🔧 Configuration

### Database Setup
The application uses PostgreSQL with the following default configuration:
- Database: `WMS_LLM`
- Schema: `wms`
- User: `wmsllm`
- Password: `1234`

You can modify these settings in `database_config.py` or use environment variables.

### User Folder Setup
Each user must have a dedicated folder for their transaction CSV files:
- The folder path is set during user registration
- Files are automatically processed and moved to an `archive` subfolder
- No duplicate processing of the same files

## 📁 File Management System

### Simplified Workflow
1. **User Registration**: Each user provides a folder path during registration
2. **File Placement**: Users place CSV files in their designated folder
3. **Automatic Processing**: Files are automatically processed on login
4. **Archive Management**: Processed files are moved to an `archive` subfolder

### CSV File Format
Required columns:
- `stock_name`: Name of the stock/company
- `ticker`: Stock ticker symbol
- `quantity`: Number of shares
- `price`: Transaction price (optional - will be fetched automatically)
- `transaction_type`: "buy" or "sell"
- `date`: Transaction date (YYYY-MM-DD format)

Optional columns:
- `channel`: Portfolio channel/account (will be extracted from filename if not provided)

### Example CSV File
```csv
stock_name,ticker,quantity,price,transaction_type,date
Reliance Industries,RELIANCE,10,2500,buy,2024-01-15
TCS,TCS,5,3500,buy,2024-01-16
Infosys,INFY,8,1500,buy,2024-01-17
```

## 🚀 Usage

1. **Start the application**:
   ```bash
   streamlit run simple_app.py
   ```

2. **Login or Register**:
   - New users must provide a folder path during registration
   - Existing users can login with their credentials

3. **File Processing**:
   - Place CSV files in your designated folder
   - Files are automatically processed on login
   - Processed files are moved to the archive folder

4. **Portfolio Analysis**:
   - View portfolio summary and performance metrics
   - Analyze holdings by stock, sector, and time period
   - Track profit/loss and portfolio allocation

## 🔐 User Management

### Admin Features
- Create and manage user accounts
- Reset user passwords
- View all users and their status
- Monitor login attempts and account lockouts

### User Features
- Secure login with password protection
- Automatic file processing from designated folder
- Personal portfolio analysis and tracking
- Session management with automatic logout

## 📊 Portfolio Analysis Features

### Summary Metrics
- Total P&L and portfolio return percentage
- Current portfolio value vs. total invested
- Number of active stocks
- Real-time price updates

### Visualizations
- Holdings by stock (bar chart)
- Profit/Loss by stock (color-coded bar chart)
- Portfolio allocation (pie chart)
- Portfolio value over time (line chart)
- Quarterly performance analysis
- Sector-wise analysis

### Data Filtering
- Filter by date range
- Filter by portfolio channel
- Filter by stock sector
- Drill-down to individual stock analysis

## 🔧 Technical Details

### Architecture
- **Frontend**: Streamlit web application
- **Backend**: Python with SQLAlchemy ORM
- **Database**: PostgreSQL with custom schema
- **Price Data**: INDmoney API with yfinance fallback
- **File Processing**: Automated CSV processing with historical price fetching

### Security Features
- Password hashing with salt
- Account lockout after failed attempts
- Session management with expiration
- Role-based access control
- SQL injection protection

### Performance Optimizations
- Cached data loading with Streamlit
- Efficient database queries
- Optimized file processing
- Background price fetching

## 🐛 Troubleshooting

### Common Issues

1. **Database Connection Error**:
   - Ensure PostgreSQL is running
   - Check database credentials in `database_config.py`
   - Verify database and schema exist

2. **File Processing Issues**:
   - Ensure CSV files have required columns
   - Check folder permissions
   - Verify folder path exists and is accessible

3. **Price Fetching Issues**:
   - Check internet connection
   - Verify ticker symbols are correct
   - Check API rate limits

### Debug Mode
Enable debug information in the sidebar to view:
- Database connection status
- File processing details
- User authentication status
- Data loading information

## 📝 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📞 Support

For support and questions:
- Check the troubleshooting section
- Review the documentation
- Create an issue on GitHub

---

**Note**: This application is designed for personal portfolio management and should not be used for professional financial advice. Always consult with qualified financial professionals for investment decisions. 