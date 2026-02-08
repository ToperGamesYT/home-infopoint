"""Sensors for Home.InfoPoint."""
from __future__ import annotations

import logging

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import HomeInfoPointDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Home.InfoPoint sensors."""
    if entry.entry_id not in hass.data[DOMAIN]:
        return
        
    coordinator: HomeInfoPointDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities = []
    
    # Static Sensor: Last Update
    entities.append(HomeInfoPointSensor(coordinator, "last_update", "Last Update", "mdi:clock-outline"))
    
    # Static Sensors: Absences
    entities.append(HomeInfoPointAbsenceSensor(coordinator, "days", "Absences (Days)", "mdi:calendar-remove"))
    entities.append(HomeInfoPointAbsenceSensor(coordinator, "unexcused_days", "Unexcused Absences (Days)", "mdi:calendar-alert"))
    entities.append(HomeInfoPointAbsenceSensor(coordinator, "hours", "Absences (Hours)", "mdi:clock-remove"))
    
    # Dynamic Sensors: Subjects
    # We will create a sensor for each subject found in the grades
    # To handle dynamic addition, we might need to check this on each update, 
    # but for now we create them at setup if data exists, or on next reload.
    # Note: Adding entities dynamically after setup requires a bit more logic or a reload.
    # For now, we add what we see.
    
    if coordinator.data and "grades" in coordinator.data:
        subjects = set(g["subject"] for g in coordinator.data["grades"])
        for subject in subjects:
            entities.append(HomeInfoPointSubjectSensor(coordinator, subject))

    async_add_entities(entities)


class HomeInfoPointSensor(CoordinatorEntity, SensorEntity):
    """Representation of a generic Home.InfoPoint Sensor."""

    def __init__(
        self,
        coordinator: HomeInfoPointDataUpdateCoordinator,
        key: str,
        name: str,
        icon: str = "mdi:school"
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._key = key
        self._attr_name = f"Home.InfoPoint {name}"
        self._attr_unique_id = f"{coordinator.entry.entry_id}_{key}"
        self._attr_icon = icon

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self.coordinator.data.get(self._key)

class HomeInfoPointAbsenceSensor(CoordinatorEntity, SensorEntity):
    """Sensor for Absences."""
    
    def __init__(self, coordinator, key, name, icon):
        super().__init__(coordinator)
        self._key = key
        self._attr_name = f"Home.InfoPoint {name}"
        self._attr_unique_id = f"{coordinator.entry.entry_id}_absence_{key}"
        self._attr_icon = icon
    
    @property
    def native_value(self):
        if not self.coordinator.data or "absences" not in self.coordinator.data:
            return None
        return self.coordinator.data["absences"].get(self._key)

class HomeInfoPointSubjectSensor(CoordinatorEntity, SensorEntity):
    """Sensor for a specific Subject (showing latest grade)."""
    
    def __init__(self, coordinator, subject):
        super().__init__(coordinator)
        self._subject = subject
        self._attr_name = f"Home.InfoPoint {subject}"
        self._attr_unique_id = f"{coordinator.entry.entry_id}_subject_{subject.replace(' ', '_')}"
        self._attr_icon = "mdi:book-open-variant"
    
    @property
    def native_value(self):
        """Return the average grade for this subject."""
        if not self.coordinator.data or "grades" not in self.coordinator.data:
            return None
            
        grades = [g for g in self.coordinator.data["grades"] if g["subject"] == self._subject]
        if not grades:
            return None
            
        # Calculate Average
        total = 0.0
        count = 0
        for g in grades:
            try:
                # Handle simple grades like "1", "2", "15"
                # If there are modifiers like "+", "-", "2-", handle them if possible or ignore
                # German grades: 1+ = 0.75? Notensystem 1-15 points? 
                # The user dump showed "2", "4", "5", "1". 
                # Let's try simple float conversion first.
                val_str = g["grade"].replace(",", ".").strip()
                # Remove common non-numeric suffixes if attached directly, though risky.
                # Use a helper or just strict float
                val = float(val_str)
                total += val
                count += 1
            except ValueError:
                pass
        
        if count == 0:
            return None
            
        return round(total / count, 2)

    @property
    def extra_state_attributes(self):
        """Return details about the grade and history."""
        if not self.coordinator.data or "grades" not in self.coordinator.data:
            return {}
            
        grades = [g for g in self.coordinator.data["grades"] if g["subject"] == self._subject]
        if not grades:
            return {}
            
        latest = grades[0]
        return {
            "latest_grade_date": latest["date"],
            "latest_grade_comment": latest["comment"],
            "latest_grade_value": latest["grade"],
            "history": grades 
        }
