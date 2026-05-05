"""
Tests for Chart API endpoints
"""

import pytest
from fastapi.testclient import TestClient
from api.main import app

client = TestClient(app)


def test_create_chart_auto_detect():
    """Test chart creation with auto-detection"""
    response = client.post(
        "/api/charts/create",
        json={
            "data": [
                {"month": "Jan", "sales": 1000, "profit": 200},
                {"month": "Feb", "sales": 1500, "profit": 300},
                {"month": "Mar", "sales": 1200, "profit": 250}
            ],
            "title": "Monthly Sales & Profit"
        }
    )

    assert response.status_code == 200
    data = response.json()

    assert data["chart_type"] in ["bar", "line"]
    assert data["x_key"] == "month"
    assert "sales" in data["y_keys"]
    assert "profit" in data["y_keys"]
    assert len(data["colors"]) == 2
    assert data["title"] == "Monthly Sales & Profit"
    assert data["legend"] is True
    assert data["grid"] is True


def test_create_chart_explicit_type():
    """Test chart creation with explicit type"""
    response = client.post(
        "/api/charts/create",
        json={
            "data": [
                {"category": "A", "value": 10},
                {"category": "B", "value": 20},
                {"category": "C", "value": 15}
            ],
            "chart_type": "pie",
            "title": "Category Distribution"
        }
    )

    assert response.status_code == 200
    data = response.json()

    assert data["chart_type"] == "pie"
    assert data["x_key"] == "category"
    assert "value" in data["y_keys"]
    assert data["title"] == "Category Distribution"


def test_create_chart_with_labels():
    """Test chart creation with custom labels"""
    response = client.post(
        "/api/charts/create",
        json={
            "data": [
                {"year": 2020, "revenue": 1000},
                {"year": 2021, "revenue": 1500},
                {"year": 2022, "revenue": 2000}
            ],
            "chart_type": "line",
            "title": "Revenue Growth",
            "x_label": "Year",
            "y_label": "Revenue ($K)"
        }
    )

    assert response.status_code == 200
    data = response.json()

    assert data["chart_type"] == "line"
    assert data["x_label"] == "Year"
    assert data["y_label"] == "Revenue ($K)"


def test_create_chart_scatter():
    """Test scatter plot creation"""
    response = client.post(
        "/api/charts/create",
        json={
            "data": [
                {"height": 170, "weight": 65},
                {"height": 180, "weight": 75},
                {"height": 165, "weight": 60},
                {"height": 175, "weight": 70}
            ],
            "chart_type": "scatter",
            "title": "Height vs Weight"
        }
    )

    assert response.status_code == 200
    data = response.json()

    assert data["chart_type"] == "scatter"
    assert data["x_key"] == "height"
    assert "weight" in data["y_keys"]


def test_create_chart_empty_data():
    """Test chart creation with empty data"""
    response = client.post(
        "/api/charts/create",
        json={
            "data": [],
            "title": "Empty Chart"
        }
    )

    # FastAPI returns 422 for validation errors (empty array violates min_length=1)
    assert response.status_code == 422


def test_analyze_chart_type():
    """Test chart type analysis"""
    response = client.post(
        "/api/charts/analyze",
        json=[
            {"product": "A", "revenue": 1000},
            {"product": "B", "revenue": 1500},
            {"product": "C", "revenue": 1200}
        ]
    )

    assert response.status_code == 200
    data = response.json()

    assert "recommended_type" in data
    assert data["recommended_type"] in ["bar", "pie"]
    assert "confidence" in data
    assert data["confidence"] in ["low", "medium", "high"]
    assert "alternatives" in data
    assert len(data["alternatives"]) > 0
    assert "config" in data
    assert "xKey" in data["config"]
    assert "yKeys" in data["config"]


def test_analyze_empty_data():
    """Test analysis with empty data"""
    response = client.post(
        "/api/charts/analyze",
        json=[]
    )

    assert response.status_code == 400


def test_get_chart_types():
    """Test getting available chart types"""
    response = client.get("/api/charts/types")

    assert response.status_code == 200
    data = response.json()

    assert "types" in data
    assert len(data["types"]) == 6  # line, bar, pie, scatter, area, radar

    # Check first type structure
    first_type = data["types"][0]
    assert "type" in first_type
    assert "name" in first_type
    assert "description" in first_type
    assert "use_cases" in first_type


def test_create_chart_with_custom_keys():
    """Test chart creation with custom x_key and y_keys"""
    response = client.post(
        "/api/charts/create",
        json={
            "data": [
                {"date": "2024-01", "sales": 1000, "costs": 800, "profit": 200},
                {"date": "2024-02", "sales": 1500, "costs": 1100, "profit": 400}
            ],
            "chart_type": "line",
            "x_key": "date",
            "y_keys": ["sales", "costs"],
            "title": "Sales vs Costs"
        }
    )

    assert response.status_code == 200
    data = response.json()

    assert data["chart_type"] == "line"
    assert data["x_key"] == "date"
    assert data["y_keys"] == ["sales", "costs"]
    assert "profit" not in data["y_keys"]


def test_create_area_chart():
    """Test area chart creation"""
    response = client.post(
        "/api/charts/create",
        json={
            "data": [
                {"quarter": "Q1", "product_a": 100, "product_b": 150, "product_c": 120},
                {"quarter": "Q2", "product_a": 120, "product_b": 180, "product_c": 140},
                {"quarter": "Q3", "product_a": 140, "product_b": 200, "product_c": 160}
            ],
            "chart_type": "area",
            "title": "Product Sales by Quarter"
        }
    )

    assert response.status_code == 200
    data = response.json()

    assert data["chart_type"] == "area"
    assert len(data["y_keys"]) == 3
    assert len(data["colors"]) == 3


def test_create_radar_chart():
    """Test radar chart creation with override"""
    response = client.post(
        "/api/charts/create",
        json={
            "data": [
                {"player": "A", "speed": 80, "strength": 70, "skill": 90},
                {"player": "B", "speed": 70, "strength": 85, "skill": 75}
            ],
            "chart_type": "radar",
            "title": "Player Comparison"
        }
    )

    assert response.status_code == 200
    data = response.json()

    assert data["chart_type"] == "radar"
    assert len(data["y_keys"]) == 3


def test_analyze_time_series():
    """Test analysis of time series data"""
    response = client.post(
        "/api/charts/analyze",
        json=[
            {"timestamp": "2024-01-01", "value": 100},
            {"timestamp": "2024-01-02", "value": 150},
            {"timestamp": "2024-01-03", "value": 120}
        ]
    )

    assert response.status_code == 200
    data = response.json()

    # Should recommend line or bar for time series
    assert data["recommended_type"] in ["line", "bar"]
    assert data["config"]["xKey"] == "timestamp"
    assert "value" in data["config"]["yKeys"]


def test_analyze_confidence_levels():
    """Test confidence levels based on data size"""
    # Small dataset (low confidence)
    response_small = client.post(
        "/api/charts/analyze",
        json=[
            {"x": 1, "y": 10},
            {"x": 2, "y": 20}
        ]
    )
    assert response_small.json()["confidence"] == "low"

    # Medium dataset
    response_medium = client.post(
        "/api/charts/analyze",
        json=[{"x": i, "y": i * 10} for i in range(5)]
    )
    assert response_medium.json()["confidence"] == "medium"

    # Large dataset (high confidence)
    response_large = client.post(
        "/api/charts/analyze",
        json=[{"x": i, "y": i * 10} for i in range(15)]
    )
    assert response_large.json()["confidence"] == "high"
