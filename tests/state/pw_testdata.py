"""Shared synthetic ProjectWise tree for the navigator test suite.

Shapes mirror the 2026-07 recon (34 projects / ~28k files): numbered
series template, consultant-parallel folders, the CADD triple, per-SFN
structure folders, and the two dominant 950-Reviews layouts.  PIDs/SFNs
are fictional.
"""

PID = "123456"
SFN = "1234567"
PATH = f"01 Active Projects\\District 06\\Franklin\\{PID}"

#: recon-shape tree (district_file_samples record["tree"] format)
TREE = {
    "name": PID, "id": 1000, "files": ["123456.cfg"],
    "children": [
        {"name": "100-Planning", "id": 1100, "files": [], "children": [
            {"name": "Scopes", "id": 1110,
             "files": [f"FRA-{PID} ODOT Scope.xlsx",
                       f"FRA-{PID} Project Initiation Package.doc"],
             "children": []},
        ]},
        {"name": "300-Survey", "id": 1300, "files": [], "children": [
            {"name": "SurveyData", "id": 1310,
             "files": ["Existing Utility Shots.csv",
                       "FRA-70 Survey Report.pdf"],
             "children": []},
        ]},
        {"name": "301-Survey_Korda", "id": 1301, "files": [], "children": [
            {"name": "SurveyData", "id": 1311,
             "files": ["Korda Field Book.pdf"], "children": []},
        ]},
        {"name": "400-Engineering", "id": 1400, "files": [], "children": [
            {"name": "Roadway", "id": 1410, "files": [], "children": [
                {"name": "Sheets", "id": 1411,
                 "files": [f"{PID}_GP001.dgn", f"{PID}_GN001.dgn"],
                 "children": []},
            ]},
            {"name": "Geotechnical", "id": 1420, "files": [], "children": [
                {"name": "EngData", "id": 1421,
                 "files": ["B-001 Boring Log.pdf"], "children": []},
            ]},
            {"name": "Structures", "id": 1430, "files": [], "children": [
                {"name": f"SFN_{SFN}", "id": 1431, "files": [], "children": [
                    {"name": "Sheets", "id": 1432,
                     "files": [f"{PID}_SFN_{SFN}_SB001.dgn",
                               f"{PID}_SFN_{SFN}_SB002.dgn"],
                     "children": []},
                    {"name": "EngData", "id": 1433,
                     "files": [f"FRA-70 Load Rating Summary_{SFN}.pdf"],
                     "children": []},
                ]},
            ]},
        ]},
        {"name": "401-Engineering_GPDgroup", "id": 1401, "files": [],
         "children": [
            {"name": "Structures", "id": 1440, "files": [], "children": [
                {"name": f"SFN_{SFN}", "id": 1441, "files": [], "children": [
                    {"name": "Sheets", "id": 1442,
                     "files": [f"{PID}_SFN_{SFN}_SB003.dgn"],
                     "children": []},
                ]},
            ]},
        ]},
        {"name": "600-Contracts", "id": 1600, "files": [], "children": [
            {"name": "03-AsAdvertised", "id": 1610,
             "files": [f"{PID}_As Advertised Plan Set.pdf"],
             "children": []},
        ]},
        {"name": "950-Reviews", "id": 1950, "files": [], "children": [
            {"name": "PlanReviews", "id": 1951, "files": [], "children": [
                {"name": "01-Stage2", "id": 1952, "files": [], "children": [
                    {"name": "01-Submission", "id": 1953,
                     "files": [f"FRA-70_PID{PID}_S2_Plan Set.pdf"],
                     "children": []},
                    {"name": "02-Comments", "id": 1954,
                     "files": [f"FRA-70_PID{PID}_S2_Comments.pdf"],
                     "children": []},
                    {"name": "03-Disposition of Comments", "id": 1955,
                     "files": [f"FRA-70_PID{PID}_S2_Dispositions.pdf",
                               f"20240201_FRA-{PID}_S2_Comment Resolution"
                               " Form.xlsx"],
                     "children": []},
                ]},
            ]},
            {"name": "Structure Type Studies", "id": 1960, "files": [],
             "children": [
                {"name": "20230801 Resubmittal", "id": 1961, "files": [],
                 "children": [
                    {"name": "Submittal", "id": 1962,
                     "files": ["FRA-70 STS Alternatives Matrix.pdf",
                               "FRA-70 Structure Type Study.pdf"],
                     "children": []},
                    {"name": "Comments", "id": 1963,
                     "files": ["FRA-70 STS Markups.pdf",
                               "FRA-70 STS Comment Dispositions.pdf"],
                     "children": []},
                ]},
            ]},
        ]},
    ],
}

RECON_RECORD = {
    "county": "Franklin", "project_folder": PID, "description": "",
    "matched_because": f"template-hit PID {PID}", "folder_id": 1000,
    "path": PATH, "n_files": 0, "budget_left": 99, "files_flat": [],
    "tree": TREE,
}


def snapshot_project():
    """A ProjectWiseProject over the synthetic tree (offline)."""
    from civilpy.state.ohio.DOT.pw_snapshot import SnapshotClient
    client, path, pid = SnapshotClient.from_recon(RECON_RECORD)
    from civilpy.state.ohio.DOT.pw_project import ProjectWiseProject
    return ProjectWiseProject(pid, path=path, client=client)
