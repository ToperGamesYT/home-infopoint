"""API Client for Home.InfoPoint."""
from __future__ import annotations

import logging
import aiohttp
from bs4 import BeautifulSoup

from .const import DEFAULT_URL

_LOGGER = logging.getLogger(__name__)

class HomeInfoPointClient:
    """Home.InfoPoint API Client."""

    def __init__(self, session: aiohttp.ClientSession, username: str, password: str, url: str = DEFAULT_URL) -> None:
        """Initialize the client."""
        self._session = session
        self._username = username
        self._password = password
        self._url = url
        if not self._url.endswith("/"):
             self._url += "/"

    async def authenticate(self) -> bool:
        """Authenticate with the Home.InfoPoint service."""
        # 1. Fetch the login page to parse the form
        start_url = f"{self._url}default.php"
        _LOGGER.debug(f"Fetching login page: {start_url}")
        
        headers = self._get_headers()

        async with self._session.get(start_url, headers=headers) as response:
            text = await response.text()
            soup = BeautifulSoup(text, "html.parser")
            
            # Find the login form
            form = soup.find("form")
            if not form:
                _LOGGER.error("Could not find login form on page")
                return False
            
            # Determine action URL
            action = form.get("action")
            if not action:
                # Submit to self if no action
                post_url = start_url
            elif action.startswith("http"):
                post_url = action
            else:
                post_url = f"{self._url}{action}"
            
            _LOGGER.debug(f"Found form, submitting to: {post_url}")

            # Prepare form data
            data = {}
            for input_tag in form.find_all("input"):
                name = input_tag.get("name")
                input_type = input_tag.get("type", "").lower()
                if not name:
                    continue
                
                value = input_tag.get("value", "")
                
                # If it's the submit button, keep original value
                if input_type == "submit":
                    data[name] = value
                    continue
                
                if ("user" in name.lower() or "login" in name.lower()) and "pass" not in name.lower():
                    data[name] = self._username
                elif "pass" in name.lower():
                     data[name] = self._password
                else:
                    data[name] = value

            # Ensure we have at least the basics if heuristics failed (fallback)
            if "username" not in data and "user" not in data:
                 data["username"] = self._username
            if "password" not in data:
                 data["password"] = self._password
            if "login" not in data: 
                 data["login"] = "Anmelden"

            
            # Add Referer
            headers["Referer"] = start_url
            
            _LOGGER.debug(f"Submitting login data (keys): {list(data.keys())}")
            
            async with self._session.post(post_url, data=data, headers=headers) as post_response:
                post_text = await post_response.text()
                
                if "Abmelden" in post_text or "Logout" in post_text:
                    _LOGGER.info("Login successful (detected Logout button)")
                    return True
                
                # Check for explicit errors
                lower_text = post_text.lower()
                if "fehler" in lower_text or "falsch" in lower_text or "nicht erfolgreich" in lower_text:
                     _LOGGER.error("Login failed: Server returned error message")
                     return False
                
                # Check for error in URL (e.g. default.php?err=user)
                if "err=" in str(post_response.url) or "error=" in str(post_response.url):
                    _LOGGER.error(f"Login failed: Redirected to error URL {post_response.url}")
                    return False
                
                # Double check with a follow-up request to default.php content
                return await self._check_logged_in()

    async def _check_logged_in(self) -> bool:
        """Check if we are effectively logged in."""
        async with self._session.get(f"{self._url}default.php", headers=self._get_headers()) as response:
             text = await response.text()
             # STRICT CHECK: Only "Abmelden" implies we are logged in.
             is_logged_in = "Abmelden" in text or "Logout" in text
             _LOGGER.debug(f"Check login status: {is_logged_in}")
             return is_logged_in

    def _get_headers(self) -> dict:
        """Return headers with User-Agent."""
        return {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }

    async def get_data(self) -> dict:
        """Fetch data from Home.InfoPoint."""
        if not await self._check_logged_in():
            if not await self.authenticate():
                raise Exception("Authentication failed")

        data = {}
        
        # Always fetch getdata.php as it contains the real data
        async with self._session.get(f"{self._url}getdata.php", headers=self._get_headers()) as response:
            text = await response.text()
            soup = BeautifulSoup(text, "html.parser")
            
            page_text = soup.get_text()
            
            # 1. Parse Last Update
            if "aktualisiert am" in page_text:
                try:
                    part = page_text.split("aktualisiert am")[1].strip().split()[0]
                    part = part.strip('"').strip("'").split("<")[0]
                    data["last_update"] = part
                except IndexError:
                    data["last_update"] = "Unknown"
            else:
                 data["last_update"] = "Connected"

            # 2. Parse Absences (Heuristic: Look for table with 'Fehltage')
            data["absences"] = {
                "days": 0,
                "unexcused_days": 0,
                "hours": "0",
                "unexcused_hours": "0"
            }
            tables = soup.find_all("table")
            for table in tables:
                rows = table.find_all("tr")
                # fast check raw text
                table_text = table.get_text()
                if "Fehltage" in table_text and "Unentschuldigte" in table_text:
                    for row in rows:
                        cols = [td.get_text(strip=True) for td in row.find_all("td")]
                        if not cols: continue
                        if "Fehltage" == cols[0] and len(cols) > 1:
                            data["absences"]["days"] = int(cols[1])
                        elif "Unentschuldigte Fehltage" == cols[0] and len(cols) > 1:
                            data["absences"]["unexcused_days"] = int(cols[1])
                        elif "Fehlstunden" == cols[0] and len(cols) > 1:
                            data["absences"]["hours"] = cols[1]
                        elif "Unentschuldigte Fehlstunden" == cols[0] and len(cols) > 1:
                            data["absences"]["unexcused_hours"] = cols[1]

            # 3. Parse Grades
            # Logic: Iterate over headers (h3, b, etc.) and find the next table
            data["grades"] = []
            
            # We look for all 'b' tags or div headers that might be subjects. 
            # In the debug dump, it identified them.
            # A robust way is to iterate over all elements and maintain "current subject" state
            
            current_subject = None
            
            # Find all relevant elements in order
            elements = soup.find_all(['h3', 'b', 'strong', 'table'])
            
            for el in elements:
                if el.name in ['h3', 'b', 'strong']:
                    text = el.get_text(strip=True)
                    # Filter out noise (Legends, etc.)
                    if len(text) > 2 and "Notenspiegel" not in text and "Endnoten" not in text and "Legende" not in text:
                        current_subject = text
                
                elif el.name == 'table':
                    if not current_subject:
                        continue
                        
                    # Check if it's a grades table (has 'Zensur' or 'Note' header)
                    headers = [th.get_text(strip=True) for th in el.find_all("th")]
                    if 'Zensur' in headers and 'Datum' in headers:
                        # Process Grades Table
                        rows = el.find_all("tr")
                        for row in rows:
                            cols = [td.get_text(strip=True) for td in row.find_all("td")]
                            if len(cols) >= 3:
                                # Found a grade!
                                # Format: Datum, Zensur, Bemerkung, ...
                                try:
                                    grade_val = cols[1]
                                    if grade_val: # Only if grade exists
                                        data["grades"].append({
                                            "subject": current_subject,
                                            "date": cols[0],
                                            "grade": grade_val,
                                            "comment": cols[2] if len(cols) > 2 else ""
                                        })
                                except:
                                    pass
                        
                        # Reset subject so we don't attribute the next table (Endnoten) to this subject 
                        # as "New Grades" (unless we want to). 
                        # Actually, keeping current_subject is fine if we want Endnoten too, 
                        # but usually headers separate them.
                        # For now, let's just assume one grade table per header.
                        # current_subject = None # Commented out to potentially capture multiple tables if needed

        return data
