@echo off
REM Update pip to the latest version
echo Updating pip...
python -m pip install --upgrade pip

REM Install required Python packages
echo Installing packages from requirements.txt...
pip install -r requirements.txt

echo All requirements installed successfully!
pause