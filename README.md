# Home.InfoPoint Custom Component for Home Assistant

This is a custom component for Home Assistant to integrate with the **Home.InfoPoint** system (e.g., typically used by schools like Carl-Zeiss-Gymnasium Jena).

## Features

- **Authentication**: Handles session-based login with specific User-Agent requirements.
- **Data Fetching**: Scrapes data from the `getdata.php` dashboard.
- **Sensors**:
  - **Last Update**: Shows when the data was last updated on the server.
  - **Absences**: Tracks total and unexcused days/hours.
  - **Grades (Subjects)**: Creates a sensor for each subject found.
    - **State**: The **average grade** (calculated from all numeric grades found).
    - **Attributes**:
        - `latest_grade_value`: The value of the most recent grade.
        - `latest_grade_date`: Date of the most recent grade.
        - `latest_grade_comment`: Comment for the most recent grade.
        - `history`: A full list of all grades for the subject.

## Installation

1.  Copy the `home_infopoint` folder into your Home Assistant's `custom_components` directory.
    - Path: `/config/custom_components/home_infopoint`
2.  Restart Home Assistant.

## Configuration

1.  Go to **Settings** > **Devices & Services**.
2.  Click **Add Integration**.
3.  Search for **Home.InfoPoint**.
4.  Enter the required details:
    - **URL**: The base URL of your Home.InfoPoint instance (e.g., `https://homeinfopoint.de/czg-jena/`).
    - **Username**: Your login username.
    - **Password**: Your login password.

## Sensors Explained

### Subject Sensors (e.g., `sensor.home_infopoint_mathematik`)
The state of these sensors represents the **Average Grade** for the subject.

**Attributes:**
```yaml
latest_grade_date: "28.09.2025"
latest_grade_comment: "LK: rationale Zahlen"
latest_grade_value: "2"
history:
  - date: "28.09.2025"
    grade: "2"
    comment: "LK..."
  - ...
```

### Absence Sensors
- `sensor.home_infopoint_absences_days`
- `sensor.home_infopoint_unexcused_absences_days`
- `sensor.home_infopoint_absences_hours`

## Troubleshooting

If sensors show "Unknown" or authentcation fails:
1.  Check your credentials.
2.  Enable debug logging in `configuration.yaml` to see parsing errors:

```yaml
logger:
  default: info
  logs:
    custom_components.home_infopoint: debug
```
