## Machine Learning Project

The project builds a full `machine-learning` `workflow—data` `ingestion`, `validation`, `preprocessing/feature engineering`, `model training`, and `evaluation` — then exposes predictions via a small `Flask` web app.

### Problem statement
- This project understands how the student's performance (test scores) is affected by other variables such as Gender, Ethnicity, Parental level of education, Lunch and Test preparation course.


### Data Collection
- Dataset Source - https://www.kaggle.com/datasets/spscientist/students-performance-in-exams?datasetId=74977
- The data consists of 8 column and 1000 rows.

### Workflows - ML Pipeline

1. Data Ingestion
2. Data Validation
3. Data Transformation
4. Model Trainer
5. Model Evaluation

### Run

```bash
# create env
conda create -p ./venv python=3.12 -y
conda activate ./venv
pip install -r requirements.txt

# Run the ML pipeline
python -m src.pipeline.train_pipeline
# Output:
# r2_square = 0.8804332983749565


# Run the application (web page)
python app.py
# Open: http://127.0.0.1:5000/predictdata
# Fill out the form on the website and send it.

# CLEAN UP
conda deactivate
conda remove -p ./venv --all
```