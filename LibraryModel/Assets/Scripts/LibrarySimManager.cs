using UnityEngine;
using System.Collections.Generic;

public class LibrarySimManager : MonoBehaviour
{
    [Header("Spawn Settings")]
    public int baseMaxStudents = 7;
    public float baseMinSpawnInterval = 8f;
    public float baseMaxSpawnInterval = 18f;

    [Header("Behavior")]
    public float minStudyTime = 30f;
    public float maxStudyTime = 90f;
    public float waterBreakChance = 0.35f;
    public float ghostChance = 0.20f;

    [Header("Group Spawning")]
    public float groupSpawnChance = 0.25f;
    public int minGroupSize = 2;
    public int maxGroupSize = 4;

    ProfessionalLibrary library;
    SimulationTimeManager simTime;
    List<SimStudent> students = new List<SimStudent>();
    HashSet<string> reserved = new HashSet<string>();
    List<GameObject> ghostBags = new List<GameObject>();
    float spawnTimer;
    float nextSpawn;
    int counter;

    public Vector3 waterCoolerPos { get; private set; }

    // Effective settings (modified by sim time)
    int effectiveMaxStudents => SimulationTimeManager.Instance != null
        ? SimulationTimeManager.Instance.GetMaxConcurrentStudents()
        : baseMaxStudents;

    float effectiveMinInterval => SimulationTimeManager.Instance != null
        ? SimulationTimeManager.Instance.GetSpawnInterval()
        : baseMinSpawnInterval;

    float effectiveMaxInterval => effectiveMinInterval * 1.5f;

    static readonly Color[] Shirts = {
        new Color(0.22f,0.38f,0.55f), new Color(0.55f,0.18f,0.20f),
        new Color(0.20f,0.45f,0.28f), new Color(0.85f,0.82f,0.75f),
        new Color(0.35f,0.35f,0.38f), new Color(0.15f,0.20f,0.38f),
        new Color(0.50f,0.32f,0.18f), new Color(0.20f,0.42f,0.50f),
        new Color(0.42f,0.35f,0.22f), new Color(0.60f,0.45f,0.55f),
    };
    static readonly Color[] Skins = {
        new Color(0.95f,0.87f,0.78f), new Color(0.82f,0.68f,0.55f),
        new Color(0.72f,0.55f,0.40f), new Color(0.58f,0.42f,0.30f),
        new Color(0.42f,0.30f,0.22f), new Color(0.78f,0.62f,0.48f),
    };
    static readonly Color[] Hairs = {
        new Color(0.08f,0.06f,0.05f), new Color(0.15f,0.10f,0.08f),
        new Color(0.32f,0.22f,0.14f), new Color(0.42f,0.18f,0.10f),
        new Color(0.38f,0.32f,0.22f),
    };
    static readonly Color[] Bags = {
        new Color(0.15f,0.15f,0.18f), new Color(0.15f,0.20f,0.35f),
        new Color(0.35f,0.35f,0.38f), new Color(0.48f,0.18f,0.15f),
        new Color(0.28f,0.32f,0.20f), new Color(0.35f,0.25f,0.15f),
    };
    static readonly Color[] Pants = {
        new Color(0.25f,0.25f,0.28f), new Color(0.15f,0.18f,0.28f),
        new Color(0.55f,0.48f,0.35f), new Color(0.12f,0.12f,0.14f),
    };
    static readonly Color[] Shoes = {
        new Color(0.18f,0.15f,0.12f), new Color(0.12f,0.12f,0.14f),
        new Color(0.35f,0.28f,0.20f), new Color(0.22f,0.22f,0.25f),
    };

    void Start()
    {
        library = FindFirstObjectByType<ProfessionalLibrary>();
        simTime = FindFirstObjectByType<SimulationTimeManager>();

        if (library != null && library.GetTotalSeats() > 0)
        {
            Initialize();
        }
        else
        {
            Debug.Log("[SimManager] Will initialize when library is ready...");
        }
    }

    void Initialize()
    {
        float hW = library.roomWidth / 2f;
        float hL = library.roomLength / 2f;
        waterCoolerPos = new Vector3(hW - 1.5f, 0, hL - 1.5f);

        nextSpawn = 2f;
        spawnTimer = 0;

        string timeInfo = simTime != null ? $" | {simTime.GetDebugInfo()}" : "";
        Debug.Log($"[SimManager] Ready. {library.GetTotalSeats()} seats available.{timeInfo}");
    }

    void Update()
    {
        // Wait for library to be ready
        if (library == null || library.GetTotalSeats() == 0)
        {
            library = FindFirstObjectByType<ProfessionalLibrary>();
            if (library != null && library.GetTotalSeats() > 0)
            {
                simTime = FindFirstObjectByType<SimulationTimeManager>();
                Initialize();
            }
            return;
        }

        // Check if library is open (during closed hours, don't spawn)
        if (simTime != null && !simTime.IsLibraryOpen())
        {
            // Still update existing students, just don't spawn new ones
            UpdateExistingStudents();
            return;
        }

        spawnTimer += Time.deltaTime;

        if (spawnTimer >= nextSpawn && students.Count < effectiveMaxStudents)
        {
            // Decide: group spawn or single spawn?
            if (Random.value < groupSpawnChance && students.Count + maxGroupSize <= effectiveMaxStudents)
            {
                SpawnGroup();
            }
            else
            {
                SpawnStudent();
            }
            spawnTimer = 0;
            nextSpawn = Random.Range(effectiveMinInterval, effectiveMaxInterval);
        }

        UpdateExistingStudents();
    }

    void UpdateExistingStudents()
    {
        for (int i = students.Count - 1; i >= 0; i--)
        {
            if (students[i] == null || students[i].state == SimStudent.S.DONE)
            {
                var st = students[i];
                if (st != null)
                {
                    if (st.willGhostLeave)
                    {
                        Debug.Log($"[SimManager] Ghost occupancy at {st.assignedSeatId}");
                    }
                    reserved.Remove(st.assignedSeatId);
                    Destroy(st.gameObject);
                }
                students.RemoveAt(i);
            }
        }
    }

    void SpawnGroup()
    {
        int groupSize = Random.Range(minGroupSize, maxGroupSize + 1);

        // Get multiple seats for the group
        var seats = GetMultipleSeats(groupSize);
        if (seats.Count < 2)
        {
            // Not enough seats, spawn single instead
            SpawnStudent();
            return;
        }

        // Determine preferred zone for clustering
        int preferredZone = simTime != null ? simTime.GetPreferredZoneForClustering() : 0;

        // Sort seats to prefer clustering in same zone
        seats.Sort((a, b) =>
        {
            int zoneA = GetSeatZone(a);
            int zoneB = GetSeatZone(b);
            if (zoneA == preferredZone && zoneB != preferredZone) return -1;
            if (zoneB == preferredZone && zoneA != preferredZone) return 1;
            return 0;
        });

        counter++;
        float hL = library.roomLength / 2f;

        // Stagger spawn positions slightly so group doesn't pile up
        for (int i = 0; i < seats.Count; i++)
        {
            string seatId = seats[i];

            GameObject go = new GameObject($"Student_{counter}_G{i}");
            // Stagger spawn position slightly
            go.transform.position = new Vector3(
                Random.Range(-0.5f, 0.5f) + i * 0.3f,
                0,
                hL - 0.5f - i * 0.2f
            );

            var sim = go.AddComponent<SimStudent>();
            sim.assignedSeatId = seatId;
            sim.walkSpeed = Random.Range(1.5f, 2.2f);
            sim.studyDuration = Random.Range(minStudyTime, maxStudyTime);
            sim.secondStudyDuration = Random.Range(15f, 40f);

            // Group members often have similar behavior patterns
            bool groupWaterBreak = Random.value < waterBreakChance;
            bool groupGhost = Random.value < ghostChance * 0.5f; // Lower ghost chance in groups
            sim.willTakeWaterBreak = groupWaterBreak;
            sim.willGhostLeave = groupGhost;

            sim.shirtColor = Pick(Shirts);
            sim.skinColor = Pick(Skins);
            sim.hairColor = Pick(Hairs);
            sim.bagColor = Pick(Bags);
            sim.pantsColor = Pick(Pants);
            sim.shoeColor = Pick(Shoes);
            sim.hasGlasses = Random.value < 0.25f;
            sim.bodyScale = Random.Range(0.95f, 1.05f);

            sim.Init(this, library);

            reserved.Add(seatId);
            students.Add(sim);
        }

        Debug.Log($"[SimManager] Spawned group of {seats.Count} students: {string.Join(", ", seats)}");
    }

    int GetSeatZone(string seatId)
    {
        var seat = library.GetSeatById(seatId);
        if (seat == null) return 0;
        return seat.zoneId;
    }

    List<string> GetMultipleSeats(int count)
    {
        var available = new List<string>();
        foreach (var s in library.allSeats)
        {
            if (!reserved.Contains(s.seatId))
                available.Add(s.seatId);
        }
        if (available.Count == 0) return new List<string>();

        // Shuffle and take first 'count'
        for (int i = available.Count - 1; i > 0; i--)
        {
            int j = Random.Range(0, i + 1);
            var temp = available[i];
            available[i] = available[j];
            available[j] = temp;
        }

        return available.GetRange(0, Mathf.Min(count, available.Count));
    }

    void SpawnStudent()
    {
        string seatId = GetRandomSeat();
        if (seatId == null) return;

        counter++;
        float hL = library.roomLength / 2f;

        GameObject go = new GameObject($"Student_{counter}");
        go.transform.position = new Vector3(Random.Range(-0.5f, 0.5f), 0, hL - 0.5f);

        var sim = go.AddComponent<SimStudent>();
        sim.assignedSeatId = seatId;
        sim.walkSpeed = Random.Range(1.5f, 2.2f);
        sim.studyDuration = Random.Range(minStudyTime, maxStudyTime);
        sim.secondStudyDuration = Random.Range(15f, 40f);
        sim.willTakeWaterBreak = Random.value < waterBreakChance;
        sim.willGhostLeave = Random.value < ghostChance;

        sim.shirtColor = Pick(Shirts);
        sim.skinColor = Pick(Skins);
        sim.hairColor = Pick(Hairs);
        sim.bagColor = Pick(Bags);
        sim.pantsColor = Pick(Pants);
        sim.shoeColor = Pick(Shoes);
        sim.hasGlasses = Random.value < 0.25f;
        sim.bodyScale = Random.Range(0.95f, 1.05f);

        sim.Init(this, library);

        reserved.Add(seatId);
        students.Add(sim);

        string behavior = sim.willTakeWaterBreak ? "will take water break" : "straight study";
        if (sim.willGhostLeave) behavior += " + GHOST";
        Debug.Log($"[SimManager] Spawned student #{counter} → {seatId} ({behavior})");
    }

    string GetRandomSeat()
    {
        var available = new List<string>();
        foreach (var s in library.allSeats)
        {
            if (!reserved.Contains(s.seatId))
                available.Add(s.seatId);
        }
        if (available.Count == 0) return null;
        return available[Random.Range(0, available.Count)];
    }

    Color Pick(Color[] palette) => palette[Random.Range(0, palette.Length)];

    void OnDestroy()
    {
        foreach (var s in students)
            if (s != null) Destroy(s.gameObject);
        students.Clear();
        reserved.Clear();
    }
}
