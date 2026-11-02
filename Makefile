run:
	python -m src.run_all
test:
	pytest -q
app:
	streamlit run app.py
