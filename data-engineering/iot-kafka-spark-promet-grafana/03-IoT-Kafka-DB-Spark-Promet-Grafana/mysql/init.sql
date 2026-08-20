CREATE TABLE IF NOT EXISTS avg_temperatures (
    id INT AUTO_INCREMENT PRIMARY KEY,
    timestamp BIGINT,
    avg_temp FLOAT,
    current_temp FLOAT
);