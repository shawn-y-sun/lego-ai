import pandas as pd
from Technic.transform import ABSDF

def test_absdf():
    # Create a simple test series
    data = [10, 15, 8, 20, 20]
    series = pd.Series(data)

    # Test periods=1 (default)
    # Expected: [NaN, abs(15-10)=5, abs(8-15)=7, abs(20-8)=12, abs(20-20)=0]
    res1 = ABSDF(series)
    expected1 = pd.Series([float('nan'), 5.0, 7.0, 12.0, 0.0])

    # Test periods=2
    # Expected: [NaN, NaN, abs(8-10)=2, abs(20-15)=5, abs(20-8)=12]
    res2 = ABSDF(series, periods=2)
    expected2 = pd.Series([float('nan'), float('nan'), 2.0, 5.0, 12.0])

    pd.testing.assert_series_equal(res1, expected1)
    pd.testing.assert_series_equal(res2, expected2)
    print("ABSDF tests passed!")

if __name__ == "__main__":
    test_absdf()
