using UnityEngine;
using UnityEngine.Networking;
using System.Collections;
using System.Text;
using System.Collections.Generic;

public class DashboardBridge : MonoBehaviour
{
    [Header("Servers")]
    public string rpiSimulatorUrl = "http://localhost:5001";
    public string edgeUrl = "http://localhost:5002";
    public float frameInterval = 1.0f;

    RailSensorController[] sensors;
    SimulationTimeManager simTime;
    ProfessionalLibrary library;
    float timer;
    int failCount;

    void Start()
    {
        InvokeRepeating("TryFindComponents", 0.5f, 2f);
    }

    void TryFindComponents()
    {
        sensors = FindObjectsByType<RailSensorController>(FindObjectsSortMode.None);
        simTime = FindFirstObjectByType<SimulationTimeManager>();
        library = FindFirstObjectByType<ProfessionalLibrary>();

        if (sensors != null && sensors.Length > 0 && simTime != null && library != null)
        {
            CancelInvoke("TryFindComponents");
            Debug.Log($"[Bridge] Ready → RPi:{rpiSimulatorUrl} Edge:{edgeUrl}");
        }
    }

    void Update()
    {
        if (sensors == null || sensors.Length == 0 || simTime == null)
        {
            Debug.Log($"[Bridge] Update skip: sensors={(sensors == null ? "null" : sensors.Length.ToString())} simTime={simTime == null}");
            return;
        }

        timer += Time.deltaTime;
        if (timer >= frameInterval)
        {
            timer = 0;
            foreach (var s in sensors)
            {
                if (s == null)
                    Debug.Log("[Bridge] sensor is null");
                else if (s.sensorRT == null)
                    Debug.Log($"[Bridge] {s.name} sensorRT is null");
                else if (!s.isAtCheckpoint)
                    Debug.Log($"[Bridge] {s.name} isAtCheckpoint=false zone={s.currentZoneIndex}");
                else
                {
                    Debug.Log($"[Bridge] Sending to RPi - sensor:{s.name} zone:{s.zoneIds[s.currentZoneIndex]} isAtCheckpoint:{s.isAtCheckpoint}");
                    StartCoroutine(SendOccupancy(s));
                }
            }
        }
    }

    IEnumerator SendOccupancy(RailSensorController sensor)
    {
        RenderTexture rt = sensor.sensorRT;
        if (rt == null) yield break;

        // Capture camera frame
        var prev = RenderTexture.active;
        RenderTexture.active = rt;
        var tex = new Texture2D(rt.width, rt.height, TextureFormat.RGB24, false);
        tex.ReadPixels(new Rect(0, 0, rt.width, rt.height), 0, 0);
        tex.Apply();
        RenderTexture.active = prev;

        byte[] jpg = tex.EncodeToJPG(75);
        Destroy(tex);
        string b64 = System.Convert.ToBase64String(jpg);

        // Get zone info
        int zoneIdx = sensor.zoneIds[sensor.currentZoneIndex];
        string zoneName = "Z" + zoneIdx;

        // Build JSON with occupancy data
        var sb = new StringBuilder();
        sb.Append("{");

        // Header info
        sb.Append("\"sensor\":\"").Append(sensor.transform.name).Append("\",");
        sb.Append("\"zone\":\"").Append(zoneName).Append("\",");
        sb.Append("\"sim_time\":\"").Append(simTime.GetFormattedTime()).Append("\",");

        // Camera frame
        sb.Append("\"frame\":\"").Append(b64).Append("\",");

        // Occupancy data - per-seat person + objects
        sb.Append("\"occupancy\":");
        sb.Append(BuildOccupancy(zoneIdx));

        sb.Append("}");

        string json = sb.ToString();

        // Send to RPi for YOLO inference + FSM processing
        StartCoroutine(Post(rpiSimulatorUrl + "/api/v1/sensor/capture", json));

        yield break;
    }

    string BuildOccupancy(int zoneId)
    {
        var seats = library.GetSeatsInZone(zoneId);
        var students = FindObjectsByType<SimStudent>(FindObjectsSortMode.None);
        var sb = new StringBuilder();

        sb.Append("{");
        bool firstSeat = true;

        foreach (var seat in seats)
        {
            string personName = null;
            string studentState = null;
            var ghostObjects = new List<string>();

            foreach (var st in students)
            {
                if (st.assignedSeatId == seat.seatId)
                {
                    // Check if student is in an active state (person is present)
                    switch (st.state)
                    {
                        case SimStudent.S.STUDY:
                        case SimStudent.S.STUDY2:
                        case SimStudent.S.SIT:
                        case SimStudent.S.SIT2:
                        case SimStudent.S.PLACE:
                        case SimStudent.S.STAND:
                        case SimStudent.S.STAND2:
                        case SimStudent.S.PACK:
                        case SimStudent.S.WALK_TO_COOLER:
                        case SimStudent.S.DRINK:
                        case SimStudent.S.WALK_BACK:
                        case SimStudent.S.USE_PHONE:
                        case SimStudent.S.PUT_AWAY_PHONE:
                        case SimStudent.S.STRETCH:
                        case SimStudent.S.YAW:
                        case SimStudent.S.TALK:
                            personName = st.name;
                            studentState = st.state.ToString();
                            break;
                    }

                    // Get ghost objects (bag, laptop, book, cup, headphones)
                    // These are independent of person presence
                    var ghosts = st.GetGhostObjects();
                    foreach (var ghost in ghosts)
                    {
                        ghostObjects.Add(ghost.objName);
                    }
                    break;
                }
            }

            if (!firstSeat) sb.Append(",");
            firstSeat = false;

            sb.Append("\"").Append(seat.seatId).Append("\":{");

            // Person info
            if (personName != null)
            {
                sb.Append("\"person\":\"").Append(personName).Append("\",");
                sb.Append("\"state\":\"").Append(studentState ?? "").Append("\"");
            }
            else
            {
                sb.Append("\"person\":null,\"state\":null");
            }

            // Ghost objects (can have multiple: bag, laptop, book, cup, headphones)
            sb.Append(",\"objects\":[");
            for (int i = 0; i < ghostObjects.Count; i++)
            {
                if (i > 0) sb.Append(",");
                sb.Append("\"").Append(ghostObjects[i]).Append("\"");
            }
            sb.Append("]");

            sb.Append("}");
        }

        sb.Append("}");
        return sb.ToString();
    }

    IEnumerator Post(string url, string json)
    {
        Debug.Log($"[Bridge] Post starting - url:{url} json_len:{json.Length}");
        var req = new UnityWebRequest(url, "POST");
        req.uploadHandler = new UploadHandlerRaw(Encoding.UTF8.GetBytes(json));
        req.downloadHandler = new DownloadHandlerBuffer();
        req.SetRequestHeader("Content-Type", "application/json");
        req.timeout = 5;
        Debug.Log($"[Bridge] Post sending request...");
        yield return req.SendWebRequest();
        Debug.Log($"[Bridge] Post request completed - result:{req.result} error:{req.error}");

        if (req.result == UnityWebRequest.Result.ConnectionError && failCount < 2)
        {
            failCount++;
            if (failCount == 1)
                Debug.LogWarning($"[Bridge] Cannot reach {url}. Start: bash scripts/start_all.sh");
        }
        else if (req.result == UnityWebRequest.Result.Success)
        {
            failCount = 0;
            Debug.Log($"[Bridge] RPi response OK");
        }
        else
        {
            Debug.LogWarning($"[Bridge] RPi error: {req.result} - {req.error}");
        }
        req.Dispose();
    }
}
