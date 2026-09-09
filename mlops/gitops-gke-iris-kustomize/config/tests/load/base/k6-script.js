import http from 'k6/http';
import { check } from 'k6';
import { Trend, Rate } from 'k6/metrics';

const BASE = __ENV.TARGET_URL || 'http://iris-api';

const predictLatency = new Trend('iris_predict_duration', true);
const lowConfidence = new Rate('iris_low_confidence');

export const options = {
  stages: [
    { duration: '30s', target: 10 },
    { duration: '1m', target: 30 },
    { duration: '1m', target: 50 },
    { duration: '2m', target: 50 },
    { duration: '1m', target: 0 },
  ],
  thresholds: {
    http_req_failed: ['rate<0.01'],
    'http_req_duration{endpoint:predict}': ['p(95)<500'],
    iris_low_confidence: ['rate<0.30'],
  },
};

// Statistics from the original Iris dataset (Fisher 1936) — mean and standard
// deviation of each feature within a class. Sampling from these distributions
// instead of a uniform one gives realistic traffic: the drift panel gets a
// sensible baseline signal, and the predicted_class distribution stays close
// to 1/3 per class.
const CLASSES = [
  { mu: [5.006, 3.428, 1.462, 0.246], sd: [0.352, 0.379, 0.174, 0.105] }, // setosa
  { mu: [5.936, 2.770, 4.260, 1.326], sd: [0.516, 0.314, 0.470, 0.198] }, // versicolor
  { mu: [6.588, 2.974, 5.552, 2.026], sd: [0.636, 0.322, 0.552, 0.275] }, // virginica
];

// Box-Muller — k6 has no built-in normal distribution.
function gaussian(mu, sd) {
  const u1 = Math.random() || 1e-9;
  const u2 = Math.random();
  const z = Math.sqrt(-2.0 * Math.log(u1)) * Math.cos(2.0 * Math.PI * u2);
  return mu + z * sd;
}

function sampleFeatures() {
  const c = CLASSES[Math.floor(Math.random() * CLASSES.length)];
  const v = c.mu.map((m, i) => Math.max(0.1, gaussian(m, c.sd[i])));
  return {
    sepal_length_cm: Number(v[0].toFixed(2)),
    sepal_width_cm: Number(v[1].toFixed(2)),
    petal_length_cm: Number(v[2].toFixed(2)),
    petal_width_cm: Number(v[3].toFixed(2)),
  };
}

export default function () {
  const res = http.post(`${BASE}/predict`, JSON.stringify(sampleFeatures()), {
    headers: { 'Content-Type': 'application/json' },
    tags: { endpoint: 'predict' },
  });

  const ok = check(res, {
    'status 200': (r) => r.status === 200,
    'has predicted_class': (r) => {
      try {
        return typeof r.json('predicted_class') === 'string';
      } catch (e) {
        return false;
      }
    },
  });

  predictLatency.add(res.timings.duration);

  if (ok) {
    try {
      lowConfidence.add(res.json('confidence') < 0.7);
    } catch (e) {
      // no confidence field — don't skew the metric
    }
  }
}

export function handleSummary(data) {
  const m = data.metrics;
  const p = (name, stat) => (m[name] && m[name].values[stat] != null ? m[name].values[stat].toFixed(1) : 'n/a');
  return {
    stdout: [
      '',
      '=== iris-api load test ===',
      `  requests:      ${m.http_reqs ? m.http_reqs.values.count : 'n/a'}`,
      `  errors:        ${m.http_req_failed ? (m.http_req_failed.values.rate * 100).toFixed(2) : 'n/a'} %`,
      `  latency p50:   ${p('http_req_duration', 'med')} ms`,
      `  latency p95:   ${p('http_req_duration', 'p(95)')} ms`,
      `  latency p99:   ${p('http_req_duration', 'p(99)')} ms`,
      `  low-conf:      ${m.iris_low_confidence ? (m.iris_low_confidence.values.rate * 100).toFixed(1) : 'n/a'} %`,
      '',
    ].join('\n'),
  };
}
