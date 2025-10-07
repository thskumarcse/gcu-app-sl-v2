# GCU Management System

A comprehensive Streamlit-based management system for Galgotias College University (GCU) that handles HR operations, examination management, and mentoring programs.

## 🎓 Features

### HR Department
- **Attendance Management**: Track and manage staff attendance with comprehensive reporting
- **Feedback System**: Collect and manage employee feedback

### Examination Management
- **Transcript Generation**: Generate student transcripts
- **Mark Sheet Creation**: Create and manage mark sheets
- **Admit Card Generation**: Generate examination admit cards
- **Results Management**: Handle examination results and all programs results

### Mentoring System
- **Mentor-Mentee Assignment**: Assign mentors to students
- **Data Input**: Input and manage mentoring data
- **Reports**: Generate comprehensive mentoring reports

## 🚀 Getting Started

### Prerequisites
- Python 3.8 or higher
- pip (Python package installer)

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/thskumarcse/gcu-app-sl.git
   cd gcu-app-sl
   ```

2. **Create a virtual environment**
   ```bash
   python -m venv venv
   ```

3. **Activate the virtual environment**
   - On Windows:
     ```bash
     venv\Scripts\activate
     ```
   - On macOS/Linux:
     ```bash
     source venv/bin/activate
     ```

4. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

5. **Run the application**
   ```bash
   streamlit run main.py
   ```

## 📋 Dependencies

- `streamlit==1.37.0` - Web application framework
- `pandas==2.2.2` - Data manipulation and analysis
- `bcrypt==4.2.0` - Password hashing
- `streamlit-option-menu==0.3.12` - Enhanced menu components
- `gspread==6.1.2` - Google Sheets API
- `google-auth==2.34.0` - Google authentication
- `python-dateutil==2.8.2` - Date utilities
- `reportlab==4.0.9` - PDF generation
- `openpyxl==3.1.5` - Excel file handling

## 🏗️ Project Structure

```
gcu-app-sl/
├── main.py                 # Main application entry point
├── login.py               # Authentication module
├── utility.py             # Utility functions
├── requirements.txt       # Python dependencies
├── README.md             # Project documentation
├── .gitignore            # Git ignore rules
├── data/                 # Data files and templates
├── output/               # Generated reports and outputs
├── images/               # Image assets
├── logo_dir/             # Logo files
├── hr_attendance.py      # HR attendance management
├── hr_feedback.py        # HR feedback system
├── exam_*.py             # Examination modules
├── mentoring_*.py        # Mentoring system modules
└── *.ipynb               # Jupyter notebooks for analysis
```

## 🔐 User Roles

The system supports multiple user roles with different access levels:

- **Admin**: Full access to all modules
- **Mentor Admin**: Access to mentoring and examination modules
- **HOD**: Access to mentoring module
- **Coordinator**: Access to mentoring module
- **Mentor**: Access to mentoring module
- **Exam**: Access to examination modules
- **HR**: Access to HR modules

## 🛠️ Development

### Development Mode
The application includes a development mode that bypasses authentication for easier testing. Set `DEV_MODE = True` in `main.py` for development.

### Configuration
- Modify `APP_CONFIG` in `main.py` for application settings
- Update user roles and permissions in `utility.py`
- Configure Google Sheets integration in respective modules

## 📊 Data Management

- **Input Data**: Place Excel/CSV files in the `data/` directory
- **Generated Reports**: Output files are saved in the `output/` directory
- **Templates**: Excel templates are stored in the `data/` directory

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📝 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 👥 Authors

- **thskumarcse** - *Initial work* - [GitHub Profile](https://github.com/thskumarcse)

## 📞 Support

For support and questions, please contact the development team or create an issue in the repository.

## 🔄 Version History

- **v1.0.0** - Initial release with HR, Examination, and Mentoring modules

---

**Note**: This is a university management system designed specifically for Galgotias College University. Please ensure you have proper authorization before using this system in a production environment.
