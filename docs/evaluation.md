# NEXUS Evaluation

Evaluation is critical to ensure that NEXUS remains robust and does not regress. 

## Metrics Tracked

- **Task Completion Rate:** Percentage of tasks successfully implemented and passed all tests.
- **Test Pass Rate:** Percentage of tests that pass on the first attempt vs after retries.
- **Number of Retries:** Average number of debugging retries required per task.
- **Execution Duration:** Total time taken from task submission to PR creation.
- **Reviewer Rejection Rate:** How often the Reviewer Agent rejects the Coder Agent's proposed changes.

## Methodology
NEXUS uses a suite of predefined, isolated software tasks (benchmarks) run against mock repositories to gather these metrics.
