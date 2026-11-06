# Free hosted demonstration

The public entrypoint is streamlit_app.py. Streamlit Community Cloud builds it
from this GitHub repository using requirements.txt and the tested constraints.
Select Python 3.13 in Advanced settings.

At startup, the process applies Alembic migrations to a temporary SQLite database,
starts the FastAPI application on a dynamically allocated loopback port, and
executes the vulnerable and secured assessments. Streamlit is the public interface.
The backend socket accepts connections inside the host only.

Visitors can inspect all scenarios, choose either synthetic target, start selected
assessments, inspect findings and export JSON, HTML and Markdown. The demonstration
has two active-run slots, two scenario workers and six accepted submissions per
minute shared across visitors.

The latest 50 assessments are shared publicly. Before accepting another run,
the scheduler removes the oldest terminal run and its dependent records in one
transaction. Startup creates fresh demonstration history. Reports should be
downloaded before leaving the app. All targets, identities and data are synthetic.
Target registration and review mutations are disabled in this mode. The settings
validator rejects remote profiles and hosted judges.

Streamlit Community Cloud provides free hosting. Its resource limits and sleep
behavior can affect availability and cold starts. The service does not provide
durable history for this demonstration. A production deployment with private
targets needs authenticated ownership and persistent storage.

For a local preview, install the dashboard extra and run the following command.

```console
streamlit run streamlit_app.py
```

Deployment uses the public GitHub repository, main branch and streamlit_app.py.
No secrets or paid model configuration are required.

[Streamlit deployment documentation](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy)
