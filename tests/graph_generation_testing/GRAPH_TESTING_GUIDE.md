# Complete Graph Testing Guide 🧪

## Step-by-Step Testing Process

### Step 1: Populate Database with Test Data

**Run the population script:**
```bash
cd "C:\Users\Zacha\Documents\Code\python\pcba database"
python populate_test_data.py
```

**You'll see:**
```
DATABASE TEST DATA POPULATION
============================================================

Configuration:
  PCBA Boards: 20
  PMT Devices: 15
  Tests per board: 3
  Date range: Last 90 days
  Clear existing: False

Proceed? (y/n):
```

**Type `y` and press Enter**

**The script will:**
- Create 20 PCBA boards (PCBA_TEST_0000 through PCBA_TEST_0019)
- Create 15 PMT devices (PMT_TEST_0000 through PMT_TEST_0014)
- Create 60 test logs (3 tests per board)
- Generate realistic measurements for each test
- Spread tests over the last 90 days

**Output shows:**
```
Creating 20 PCBA boards...
✓ Created 20 PCBA boards

Creating 15 PMT devices...
✓ Created 15 PMT devices

Creating test logs (3 per board)...
  Created 10 test logs...
  Created 20 test logs...
  ...
✓ Created 60 test logs

DATA POPULATION COMPLETE
============================================================

Database Statistics:
  - PCBA Boards: 20
  - PMT Devices: 15
  - Test Logs: 60
  - Completed Tests: 60
  - Passed Tests: 52

Available Measurements (10):
  - Current Draw 3.3V
  - Current Draw 5V
  - Efficiency
  - Noise Level
  - Output Voltage 12V
  - Output Voltage 3.3V
  - Output Voltage 5V
  - Response Time
  - Ripple Voltage
  - Temperature

✓ Ready for graph testing!
```

### Step 2: View the Data

**Run the data viewer:**
```bash
python view_test_data.py
```

**Interactive menu appears:**
```
DATABASE VIEWER - MENU
============================================================

1. Show Summary
2. Show PCBA Boards
3. Show PMT Devices
4. Show Recent Test Logs
5. Show Available Measurements
6. Show Measurement Details
7. Show Test Fixtures
8. Exit

Select option (1-8):
```

**Try these options:**

**Option 1 - Summary:**
Shows overall statistics
```
DATABASE SUMMARY
============================================================

Overall Statistics:
  Total PCBA Boards: 20
  Total PMT Devices: 15
  Total Test Logs: 60
  Completed Tests: 60
  Passed Tests: 52
  Pass Rate: 86.7%
```

**Option 5 - Available Measurements:**
```
AVAILABLE MEASUREMENTS
============================================================

Found 10 unique measurements:

  Output Voltage 5V
    Total: 60 measurements
    Pass Rate: 95.0%
    Range: 4.970 - 5.030 V
    Average: 4.998 V

  Output Voltage 3.3V
    Total: 60 measurements
    Pass Rate: 91.7%
    Range: 3.253 - 3.348 V
    Average: 3.300 V

  ...
```

**Option 6 - Measurement Details:**
Shows individual data points
```
Enter measurement name: Output Voltage 5V
How many to show? (default: 10): 10

MEASUREMENT DETAILS: Output Voltage 5V
============================================================

Value      Unit   Result   PCBA Serial        Fixture            Date
------------------------------------------------------------------------------------------
5.002      V      PASS     PCBA_TEST_0015     Test Fixture A     2025-11-03 14:23
4.998      V      PASS     PCBA_TEST_0007     Test Fixture B     2025-11-02 09:15
4.955      V      FAIL     PCBA_TEST_0003     Test Fixture C     2025-10-28 16:45
...
```

**Quick view commands:**
```bash
# Just show summary
python view_test_data.py --summary

# Just show measurements
python view_test_data.py --measurements

# Show details for specific measurement
python view_test_data.py --detail "Output Voltage 5V"
```

### Step 3: Test the Graphs

**Run the application:**
```bash
python src/main.py
```

**You should see:**
```
INFO - Starting PCBA Database Application
INFO - ✓ Database manager created successfully
INFO - GraphPage initialized
INFO - ✓ Application started
```

**Now test these scenarios:**

#### Test 1: Basic Scatter Plot
1. Click **Graphs** tab
2. In measurement dropdown, select **"Output Voltage 5V"**
3. Click **Generate** (or Apply button)
4. **Progress dialog appears**: "Querying database..."
5. **Graph appears** with ~60 data points
6. **Verify:**
   - ✅ Points are visible
   - ✅ X-axis shows indices (0, 1, 2, ...)
   - ✅ Y-axis shows voltage values
   - ✅ Red/green spec lines visible (upper/lower limits)
   - ✅ Legend shows in top-right

#### Test 2: Interactive Features
**On the graph you just created:**

**Hover over point:**
- ✅ Point grows larger (highlights)
- ✅ No tooltip yet (v4 feature: hover only highlights)

**Click on point:**
- ✅ Tooltip appears showing:
  - Measurement name
  - Value with unit
  - Limits
  - Nominal
  - Result (PASS/FAIL)
  - PCBA Serial
  - PMT Serial
  - Test Fixture
  - Date

**Right-click on point:**
- ✅ Context menu appears with:
  - Delete Point
  - Undo Deletions (0)
  - View All
  - Export Image...

**Try Delete Point:**
- ✅ Point disappears
- ✅ Graph updates

**Right-click again:**
- ✅ "Undo Deletions (1)" shows count

**Click Undo:**
- ✅ Point reappears

**Mouse wheel:**
- ✅ Zoom in/out

**Click and drag:**
- ✅ Pan around

#### Test 3: Different Measurements
Try graphing each of these and verify they work:
- [ ] Output Voltage 3.3V
- [ ] Output Voltage 12V
- [ ] Current Draw 5V
- [ ] Current Draw 3.3V
- [ ] Temperature
- [ ] Efficiency
- [ ] Response Time
- [ ] Ripple Voltage
- [ ] Noise Level

**For each, verify:**
- ✅ Different Y-axis labels
- ✅ Different units in tooltip
- ✅ Appropriate value ranges
- ✅ Some passing, some failing measurements

#### Test 4: Pass/Fail Visualization
1. Graph **"Output Voltage 5V"**
2. Look for red points (failures) vs other colors (passes)
3. Click on a red point
4. **Verify tooltip shows**: Result: ✗ FAIL
5. Click on a green/blue point
6. **Verify tooltip shows**: Result: ✓ PASS

#### Test 5: Multiple Graphs
1. Generate a graph for "Output Voltage 5V"
2. Select "Output Voltage 3.3V"
3. Generate again
4. **Verify:**
   - ✅ Old graph is replaced
   - ✅ New graph appears
   - ✅ No memory leaks (old graph cleaned up)

#### Test 6: Spec Lines
1. Graph any voltage measurement
2. **Verify red lines visible:**
   - ✅ Lower limit line (e.g., 4.95V for 5V output)
   - ✅ Upper limit line (e.g., 5.05V for 5V output)
3. **Zoom in to see clearly:**
   - ✅ Lines span full width of plot
   - ✅ Some points above/below lines (failures)

#### Test 7: Legend
1. Graph any measurement
2. **Verify legend in top-right:**
   - ✅ Solid background (not transparent)
   - ✅ Border visible
   - ✅ Shows series names
   - ✅ Shows spec lines

#### Test 8: Graph Types (If implemented)
If you connected the Graph Type dropdown:
1. Select "Standard Plotting" → Generates scatter plot
2. Select "Comparison Plotting" → Would show comparison mode
3. Select "Relational Plotting" → Would show relationships

### Step 4: Advanced Testing

#### Test Different Date Ranges
The test data is spread over 90 days. You could add date filters to test:
- Last 7 days
- Last 30 days  
- Last 90 days
- Custom range

#### Test Multiple Fixtures
Data has 3 fixtures (A, B, C). Add fixture filter to compare:
- Fixture A vs Fixture B
- All fixtures on one graph

#### Test Search/Filter
If you add search functionality:
- Filter by PCBA serial
- Filter by PMT serial
- Filter by batch

## Custom Population Options

### More Data:
```bash
# Create 50 boards, 30 PMTs, 5 tests each, over 180 days
python populate_test_data.py --boards 50 --pmts 30 --tests 5 --days 180
```

### Clear and Repopulate:
```bash
# Clear old test data and create fresh
python populate_test_data.py --clear
```

### Minimal Test Set:
```bash
# Just 10 boards for quick testing
python populate_test_data.py --boards 10 --pmts 5 --tests 2 --days 30
```

## Verification Checklist

### Database Layer ✅
- [x] Database created successfully
- [x] Test data populated
- [x] Can view data with viewer
- [x] All measurements present
- [x] Pass/fail data realistic

### GUI Integration ✅
- [ ] Application starts
- [ ] Database manager initializes
- [ ] GraphPage initializes
- [ ] Navigate to Graphs tab
- [ ] Measurement dropdown populated
- [ ] Generate button works

### Graph Generation ✅
- [ ] Progress dialog appears
- [ ] Query runs in background
- [ ] Graph generates in background
- [ ] Plot displays correctly
- [ ] No GUI freezing

### Interactive Features ✅
- [ ] Hover highlights points
- [ ] Click shows tooltip
- [ ] Right-click shows menu
- [ ] Can delete points
- [ ] Can undo deletions
- [ ] Zoom works
- [ ] Pan works

### Visual Features ✅
- [ ] Spec lines visible
- [ ] Legend shows
- [ ] Proper axis labels
- [ ] Units displayed
- [ ] Theme matches (dark ocean)

### Data Accuracy ✅
- [ ] Correct values in tooltips
- [ ] Proper units shown
- [ ] Pass/fail correctly identified
- [ ] Dates correct
- [ ] Serial numbers correct
- [ ] Fixtures correct

## Troubleshooting

### "No measurements found"
**Cause:** Database is empty
**Fix:** Run `python populate_test_data.py`

### "Measurement dropdown is empty"
**Cause:** GraphPage not loading specs
**Fix:** Check logs for errors in `load_spec_names()`

### "Graph not appearing"
**Cause:** Button not connected
**Fix:** Find correct button name in UI and update `graph_page.py` line 77

### "Progress dialog stays open"
**Cause:** Worker not finishing
**Fix:** Check logs for database query errors

## Success Criteria

✅ **Database populated**: 20 boards, 15 PMTs, 60 test logs, 10 measurements
✅ **Can view data**: Viewer shows all data correctly
✅ **Application starts**: No errors in console
✅ **Graphs generate**: Progress dialog → Graph appears
✅ **Interactions work**: Click, hover, right-click, zoom, pan
✅ **Data accurate**: Tooltips show correct information
✅ **Performance good**: No freezing, smooth interactions
✅ **Memory clean**: Old graphs replaced properly

## What to Look For

### Good Signs 👍
- Progress dialog completes quickly (< 5 seconds for 60 measurements)
- Graph appears immediately after generation
- Smooth zoom/pan
- Tooltips appear instantly on click
- No console errors

### Bad Signs 👎
- GUI freezes during generation
- Progress dialog never closes
- Graph doesn't appear
- Console shows errors
- Memory usage keeps growing

## Next Steps After Testing

Once all tests pass:
1. **Add more filters** - Date range, fixture, serial number
2. **Add comparison mode** - Compare fixtures
3. **Add export** - Save graphs as PNG
4. **Add multiple plots** - Show several measurements at once
5. **Add reports page** - Excel export integration

You're all set for comprehensive graph testing! 🎉
