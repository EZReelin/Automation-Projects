# 7-Day Integrated Training Protocol - Workout Tracker

A comprehensive web-based workout tracking application designed specifically for the 7-Day Integrated Training Protocol with standardized core work, dart practice integration, and progressive overload.

## Features

### 🗓️ Weekly Schedule View
- Visual weekly calendar with all 7 days
- Quick overview of each day's activities
- Completion status tracking
- Today's workout highlighted

### 💪 Detailed Workout Tracking
- **Lower Body Workouts** (Monday & Friday)
  - Machine-based leg exercises
  - Weight and rep tracking
  - Progress logging

- **Upper Pull & Posterior** (Wednesday)
  - Cable and machine exercises
  - Detailed set/rep tracking

- **Running Protocols** (Tuesday, Thursday, Saturday)
  - Interval training tracking
  - Distance run logging
  - Tempo/recovery options
  - Time, distance, and pace tracking

- **Core + Mobility** (Sunday)
  - Light mobility routine
  - Core work tracking

### ⏱️ Core Routine Timer
- Built-in timer for the standardized 10-minute core routine
- 6 exercises with automatic progression:
  - Front Plank
  - Side Plank
  - Pallof Press
  - Hanging Knee Raise
  - Cable Rotation
  - Bicycle Crunch
- Automatic set/rest period management
- Audio/visual cues for exercise transitions
- Week 5-8 progression automatically applied

### 📊 Progress Tracking
- Workout history log
- Weekly completion metrics
- Training week progression (Baseline → Progression)
- Exercise data history
- Personal records tracking

### 📝 Workout Notes
- Daily workout notes
- Dart practice impact tracking
- Grip fatigue logging
- Competition day adjustments

### 🎯 Dart Practice Integration
- Specific recommendations for high dart volume days
- Core routine adjustments for competition
- Grip fatigue modifications
- Pre-competition protocols

## How to Use

### Getting Started

1. **Open the App**
   - Simply open `index.html` in any modern web browser
   - No installation or server required
   - Works on desktop, tablet, and mobile devices

2. **Select Your Training Week**
   - Use the week selector at the top to choose between:
     - Week 1-4 (Baseline)
     - Week 5-8 (Progression)
   - The app automatically adjusts exercise parameters

### Daily Workflow

1. **View Weekly Schedule**
   - Click on any day to view the full workout
   - See at a glance which workouts are completed (green checkmark)

2. **Complete a Workout**
   - Click on the day's workout
   - Follow the structured sections (Warm-up → Main Work → Core)
   - Check off exercises as you complete them
   - For strength exercises: Log weight used and reps completed
   - For running: Track time, distance, and pace

3. **Use the Core Timer**
   - Click "Start Timer" to begin the core routine
   - Timer automatically cycles through:
     - Exercise work period
     - Rest period
     - Next exercise
   - Manual controls available (Pause, Reset, Next Exercise)

4. **Track Running Workouts**
   - **Tuesday (Intervals)**: Log number of intervals completed, total time
   - **Thursday (Distance)**: Record distance and time
   - **Saturday (Tempo/Recovery)**: Select workout type and log metrics

5. **Add Notes**
   - Document dart practice duration
   - Note any grip fatigue or adjustments made
   - Track how training affects dart performance
   - Record general observations

6. **Mark Workout Complete**
   - Click "Mark Workout Complete" when finished
   - Workout is logged to your history
   - Day card shows completion badge

### Progress Tracking

1. **View Progress Tab**
   - See total workouts completed
   - Track this week's workout count
   - Review workout history (last 20 sessions)

2. **Monitor Key Metrics** (Week 4 Assessment)
   - Front Plank: Target 60+ sec by week 4
   - Hanging Knee Raise: Target 12+ reps by week 4
   - 5K run time progression
   - Leg Press working weight increases

### Adjustments for Dart Practice

The app includes built-in guidance for:

- **High Volume Days** (>2 hours dart practice)
  - Reduced core routine (5 min instead of 10)
  - Modified exercise selection

- **Competition Days** (within 24 hours)
  - Skip strength/running training
  - 50% core volume
  - Focus on mobility

- **Grip Fatigue**
  - Replace Hanging Knee Raise with Lying Leg Raise
  - Reduce Pallof Press volume

## Data Management

### Local Storage
- All data is stored locally in your browser
- No account or internet connection required
- Data persists between sessions

### Reset Data
- Use "Reset All Data" button to start fresh
- Warning: This action cannot be undone
- Useful for starting a new training cycle

### Export Data (Manual)
- Data is stored in browser localStorage
- Can be backed up using browser developer tools
- Key: `workoutTrackerData`

## Training Weeks Explained

### Weeks 1-4: Baseline Phase
- Establish movement patterns
- Build core endurance base
- Standard exercise parameters
- Focus on consistency and form

### Weeks 5-8: Progression Phase
- Increased volume/intensity
- Core exercises automatically progress:
  - Front Plank: 45s → 60s
  - Side Plank: 30s → 45s
  - Pallof Press: 12 reps → 15 reps
  - Hanging Knee Raise: 10 reps → 12 reps
  - Cable Rotation: 12 reps → 15 reps
  - Bicycle Crunch: 20 reps → 25 reps

## Exercise Reference

### Cable Setup Guide

**Pallof Press**
- Set cable at chest height
- Use D-handle attachment
- Stand perpendicular to machine, feet shoulder-width
- Press handle straight out from chest, hold 2 sec, return
- Resist rotation toward machine

**Cable Rotation**
- Set cable at chest height
- Use D-handle or rope attachment
- Stand perpendicular to machine, feet wider than shoulders
- Rotate torso away from machine, arms extended
- Control return

**Hanging Knee Raise**
- Use pull-up bar or captain's chair station
- Hang with straight arms (or use arm pads if available)
- Raise knees to 90 degrees, pause, lower controlled
- **Alternative**: Lying leg raises on mat if no equipment

## Tips for Success

1. **Daily Core Consistency**
   - Execute the core routine every single day
   - 4+ weeks of identical stimulus for neural adaptation
   - Don't skip even on rest days

2. **Track Everything**
   - Log weights used for strength exercises
   - Record running times and distances
   - Note how you feel
   - Track dart practice impact

3. **Progressive Overload**
   - Increase leg press by 10-20 lbs per week
   - Gradually build running distance
   - Progress from Week 1-4 to Week 5-8 parameters

4. **Listen to Your Body**
   - Use adjustment protocols when fatigued
   - Reduce volume on competition days
   - Note grip fatigue and modify accordingly

5. **Maintain the Schedule**
   - Follow the exact weekly structure
   - Don't swap workout days
   - Recovery days are part of the program

## Browser Compatibility

- ✅ Chrome/Edge (recommended)
- ✅ Firefox
- ✅ Safari
- ✅ Mobile browsers (iOS/Android)

## Technical Details

- **Technology**: Vanilla HTML/CSS/JavaScript
- **Storage**: Browser localStorage API
- **Size**: Single file, ~50KB
- **Offline**: Fully functional without internet
- **Responsive**: Works on all screen sizes

## Troubleshooting

### Data Not Saving
- Ensure browser localStorage is enabled
- Check if private/incognito mode is enabled (localStorage may not persist)
- Try a different browser

### Timer Not Working
- Ensure JavaScript is enabled
- Refresh the page
- Check browser console for errors

### Lost Data
- Data is stored per browser/device
- If you cleared browser data, it may be lost
- Use same browser/device for consistency

## Future Enhancements

Potential features for future versions:
- Data export to CSV/JSON
- Charts and graphs for progress visualization
- Custom exercise notes per set
- Photo progress tracking
- Workout reminders
- Dark mode

## Credits

Based on the 7-Day Integrated Training Protocol with standardized core work, designed for dart players integrating strength, running, and sport-specific practice.

## License

Personal use - Feel free to modify for your own training needs!

---

**Ready to start your training?** Open `index.html` and begin your first workout! 💪🎯
