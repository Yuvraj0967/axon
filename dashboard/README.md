# Dashboard (Person 3)

    pip install -r requirements.txt
    python make_mock.py                              # creates mock_readings.csv
    USE_MOCK=1 streamlit run app.py                  # develop without a backend
    BACKEND_IP=<LAPTOP2_IP> streamlit run app.py     # against the real API
