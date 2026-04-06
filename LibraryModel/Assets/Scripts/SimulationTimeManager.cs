using UnityEngine;

/// <summary>
/// Manages simulation time independently from real-time.
/// Provides time-of-day detection, semester modes, and crowd multipliers.
/// Attach to one GameObject in the scene (e.g., LibrarySimManager).
/// </summary>
public class SimulationTimeManager : MonoBehaviour
{
    public static SimulationTimeManager Instance { get; private set; }

    [Header("Simulation Time (in sim-seconds)")]
    [Tooltip("Start time in seconds (7am = 25200)")]
    public float simTime = 25200f; // 7:00 AM

    [Header("Time Control")]
    public float speedMultiplier = 1f;
    public bool isPaused;

    [Header("Semester Mode")]
    public SemesterMode semesterMode = SemesterMode.Normal;

    // Semester modes for controlling crowd patterns
    public enum SemesterMode { Normal, DeadWeek, FinalsWeek, Break }

    [Header("Day Length (sim-seconds)")]
    [Tooltip("How long one full day lasts in sim-time (default: 16 hours = 57600s)")]
    public float dayLength = 57600f;

    [Header("Operating Hours")]
    public float openHour = 7f;    // 7 AM
    public float closeHour = 23f;   // 11 PM

    // Events
    public System.Action<float> OnHourChanged; // fires when sim-hour changes
    public System.Action OnDayChanged;
    public System.Action<TimeOfDay> OnTimeOfDayChanged;

    // Time of day enum - placed before usage
    public enum TimeOfDay
    {
        EarlyMorning,  // 6-8 AM
        Morning,       // 8-11 AM
        Midday,        // 11 AM-1 PM
        Afternoon,     // 1-5 PM
        Evening,       // 5-8 PM
        Night,         // 8-11 PM
        LateNight      // 11 PM-6 AM (closed)
    }

    // Cached values
    float _lastHour = -1f;
    TimeOfDay _lastTimeOfDay = TimeOfDay.EarlyMorning;
    int _lastDay = -1;

    void Awake()
    {
        if (Instance != null && Instance != this)
        {
            Destroy(gameObject);
            return;
        }
        Instance = this;

        // Keep simulation running even when Unity window is not focused
        Application.runInBackground = true;
        Debug.Log("[SimTime] Run In Background = true");
    }

    void Update()
    {
        if (isPaused) return;

        float delta = Time.deltaTime * speedMultiplier;
        simTime += delta;

        // Wrap around at day length
        if (simTime >= dayLength)
        {
            simTime -= dayLength;
            OnDayChanged?.Invoke();
            _lastDay = GetSimDay();
        }

        CheckHourAndTimeOfDayChange();
    }

    void CheckHourAndTimeOfDayChange()
    {
        float hour = GetSimHour();

        if ((int)hour != (int)_lastHour)
        {
            OnHourChanged?.Invoke(hour);
        }

        TimeOfDay currentTod = GetTimeOfDay();
        if (currentTod != _lastTimeOfDay)
        {
            _lastTimeOfDay = currentTod;
            OnTimeOfDayChanged?.Invoke(currentTod);
        }

        _lastHour = hour;
    }

    // ==================== PUBLIC API ====================

    /// <summary>
    /// Current hour in sim-time (0-23.99)
    /// </summary>
    public float GetSimHour()
    {
        return (simTime / dayLength) * 24f;
    }

    /// <summary>
    /// Current minute in sim-time (0-59)
    /// </summary>
    public float GetSimMinute()
    {
        float hourFraction = GetSimHour();
        return (hourFraction - Mathf.Floor(hourFraction)) * 60f;
    }

    /// <summary>
    /// Get formatted time string (e.g., "14:35")
    /// </summary>
    public string GetFormattedTime()
    {
        int h = Mathf.FloorToInt(GetSimHour()) % 24;
        int m = Mathf.FloorToInt(GetSimMinute());
        return $"{h:D2}:{m:D2}";
    }

    /// <summary>
    /// Day counter (starts at day 1)
    /// </summary>
    public int GetSimDay()
    {
        return Mathf.FloorToInt(simTime / dayLength) + 1;
    }

    /// <summary>
    /// Is the library currently open?
    /// </summary>
    public bool IsLibraryOpen()
    {
        float hour = GetSimHour();
        return hour >= openHour && hour < closeHour;
    }

    /// <summary>
    /// Returns current time of day category
    /// </summary>
    public TimeOfDay GetTimeOfDay()
    {
        float hour = GetSimHour();

        if (hour < 6f) return TimeOfDay.LateNight;
        if (hour < 8f) return TimeOfDay.EarlyMorning;
        if (hour < 11f) return TimeOfDay.Morning;
        if (hour < 13f) return TimeOfDay.Midday;
        if (hour < 17f) return TimeOfDay.Afternoon;
        if (hour < 20f) return TimeOfDay.Evening;
        if (hour < 23f) return TimeOfDay.Night;
        return TimeOfDay.LateNight;
    }

    /// <summary>
    /// Returns 0.0 to 2.0 crowd multiplier based on time and semester
    /// </summary>
    public float GetCrowdMultiplier()
    {
        float hour = GetSimHour();

        // Base multiplier by hour
        float baseMult = GetBaseCrowdByHour(hour);

        // Semester adjustments
        switch (semesterMode)
        {
            case SemesterMode.DeadWeek:
                baseMult *= 1.3f;
                break;
            case SemesterMode.FinalsWeek:
                baseMult *= 1.5f;
                break;
            case SemesterMode.Break:
                baseMult *= 0.4f;
                break;
            // Normal: no change
        }

        // During closed hours, multiplier drops to near zero
        if (!IsLibraryOpen())
        {
            baseMult *= 0.1f;
        }

        return Mathf.Clamp(baseMult, 0f, 2f);
    }

    float GetBaseCrowdByHour(float hour)
    {
        // Hour -> base crowd multiplier (0-2)
        // Based on expected library usage patterns
        if (hour < 6f) return 0.05f;
        if (hour < 7f) return 0.1f;
        if (hour < 8f) return 0.25f;
        if (hour < 9f) return 0.4f;
        if (hour < 10f) return 0.55f;
        if (hour < 11f) return 0.6f;
        if (hour < 12f) return 0.65f;    // Late morning
        if (hour < 13f) return 0.55f;    // Lunch dip
        if (hour < 14f) return 0.6f;
        if (hour < 15f) return 0.5f;
        if (hour < 16f) return 0.45f;
        if (hour < 17f) return 0.55f;    // After class
        if (hour < 18f) return 0.75f;    // Early evening rush
        if (hour < 19f) return 0.9f;     // Peak evening
        if (hour < 20f) return 0.85f;
        if (hour < 21f) return 0.7f;
        if (hour < 22f) return 0.45f;    // Late night drop
        if (hour < 23f) return 0.25f;
        return 0.05f;
    }

    /// <summary>
    /// Returns max concurrent students for current time
    /// </summary>
    public int GetMaxConcurrentStudents()
    {
        float hour = GetSimHour();

        int baseMax = 7;

        TimeOfDay tod = GetTimeOfDay();
        switch (tod)
        {
            case TimeOfDay.Morning:    baseMax = 6; break;
            case TimeOfDay.Midday:     baseMax = 8; break;
            case TimeOfDay.Afternoon:  baseMax = 6; break;
            case TimeOfDay.Evening:    baseMax = 10; break;
            case TimeOfDay.Night:      baseMax = 5; break;
            default:                   baseMax = 4; break;
        }

        // Scale with semester
        switch (semesterMode)
        {
            case SemesterMode.DeadWeek:    baseMax = Mathf.RoundToInt(baseMax * 1.3f); break;
            case SemesterMode.FinalsWeek:  baseMax = Mathf.RoundToInt(baseMax * 1.5f); break;
            case SemesterMode.Break:       baseMax = Mathf.RoundToInt(baseMax * 0.4f); break;
        }

        return Mathf.Clamp(baseMax, 2, 15);
    }

    /// <summary>
    /// Get spawn interval base (seconds between spawns)
    /// </summary>
    public float GetSpawnInterval()
    {
        float crowd = GetCrowdMultiplier();

        // When crowd is high (1.5+), spawn more frequently
        // When crowd is low (0.3-), spawn less frequently
        float baseInterval = 13f; // average seconds
        float interval = baseInterval / crowd;

        // Clamp to reasonable range (3s to 30s)
        return Mathf.Clamp(interval, 3f, 30f);
    }

    /// <summary>
    /// Get target zone preference (returns zone ID for clustering)
    /// </summary>
    public int GetPreferredZoneForClustering()
    {
        // During high traffic, prefer zones 1-2 (back, quieter)
        // During low traffic, prefer zones 5-7 (front, more social)
        float crowd = GetCrowdMultiplier();
        if (crowd > 1.0f) return Random.Range(1, 3); // Back zones
        return Random.Range(5, 8); // Front zones
    }

    /// <summary>
    /// Set simulation time (for testing/debugging)
    /// </summary>
    public void SetSimTime(float newTime)
    {
        simTime = Mathf.Clamp(newTime, 0f, dayLength - 1f);
        CheckHourAndTimeOfDayChange();
    }

    /// <summary>
    /// Advance time by N sim-minutes (for UI controls)
    /// </summary>
    public void AdvanceTime(float simMinutes)
    {
        float secondsToAdd = (simMinutes / 60f) * dayLength;
        SetSimTime(simTime + secondsToAdd);
    }

    /// <summary>
    /// Pause/unpause simulation
    /// </summary>
    public void SetPaused(bool paused)
    {
        isPaused = paused;
    }

    /// <summary>
    /// Set speed multiplier (0.1 to 60)
    /// </summary>
    public void SetSpeed(float speed)
    {
        speedMultiplier = Mathf.Clamp(speed, 0.1f, 60f);
    }

    /// <summary>
    /// Set semester mode
    /// </summary>
    public void SetSemesterMode(SemesterMode mode)
    {
        semesterMode = mode;
        Debug.Log($"[SimTime] Semester mode set to: {mode}");
    }

    /// <summary>
    /// Get debug info string
    /// </summary>
    public string GetDebugInfo()
    {
        return $"[SimTime] {GetFormattedTime()} | Day {GetSimDay()} | {GetTimeOfDay()} | Crowd: {GetCrowdMultiplier():F2}x | Max: {GetMaxConcurrentStudents()} | {(isPaused ? "PAUSED" : $"{speedMultiplier:F1}x")}";
    }

    // GUI for debugging (optional)
    void OnGUI()
    {
        // Uncomment to show debug panel in-game
        /*
        GUILayout.BeginArea(new Rect(10, 10, 400, 200));
        GUILayout.Label(GetDebugInfo());

        if (GUILayout.Button(isPaused ? "Resume" : "Pause", GUILayout.Width(80)))
        {
            isPaused = !isPaused;
        }

        GUILayout.BeginHorizontal();
        if (GUILayout.Button("0.5x", GUILayout.Width(50))) SetSpeed(0.5f);
        if (GUILayout.Button("1x", GUILayout.Width(50))) SetSpeed(1f);
        if (GUILayout.Button("2x", GUILayout.Width(50))) SetSpeed(2f);
        if (GUILayout.Button("10x", GUILayout.Width(50))) SetSpeed(10f);
        GUILayout.EndHorizontal();

        GUILayout.BeginHorizontal();
        if (GUILayout.Button("Normal")) SetSemesterMode(SemesterMode.Normal);
        if (GUILayout.Button("Dead Week")) SetSemesterMode(SemesterMode.DeadWeek);
        if (GUILayout.Button("Finals")) SetSemesterMode(SemesterMode.FinalsWeek);
        GUILayout.EndHorizontal();

        GUILayout.EndArea();
        */
    }
}