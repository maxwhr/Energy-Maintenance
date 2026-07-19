import fs from 'node:fs';
import path from 'node:path';

const root = path.resolve(import.meta.dirname, '..', '..');
const artifact = path.join(root, '.runtime', 'task25b_r3_dev_r2', 'browser.json');
if (!fs.existsSync(artifact)) throw new Error(`missing browser evidence: ${artifact}`);
const evidence = JSON.parse(fs.readFileSync(artifact, 'utf8'));
const required = ['v2_failure_preserved', 'v3_independent', 'raw_surfaced_separated', 'model_coverage_visible', 'alarm_coverage_visible', 'vector_heavy_visible', 'mode_distinctness_visible', 'viewer_read_only', 'no_secret_rendered'];
const checks = new Map((evidence.checks || []).map((item) => [item.name, item]));
const failed = required.filter((name) => !checks.get(name)?.passed);
if ((evidence.console_errors || []).length) failed.push('console_errors');
if ((evidence.page_errors || []).length) failed.push('page_errors');
if ((evidence.network_failures || []).length) failed.push('network_failures');
console.log(JSON.stringify({ status: failed.length ? 'FAILED' : 'PASSED', checks: checks.size, failed }, null, 2));
if (failed.length) process.exitCode = 1;
