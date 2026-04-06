using UnityEngine;
using UnityEngine.UI;
using System.Collections.Generic;

public class RailSensorController : MonoBehaviour
{
    [Header("Timing")]
    public float moveSpeed = 2.0f;
    public float scanDuration = 3.0f;
    public float calibrationSpeed = 0.8f;

    [Header("Sensor")]
    public float cameraFOV = 110f;
    public int renderSize = 256;

    public enum Phase { Calibrating, Scanning }
    public Phase phase { get; private set; } = Phase.Calibrating;

    [Header("Debug")]
    public bool skipCalibration = false;

    public string statusText { get; private set; } = "INITIALIZING";
    public int currentZoneIndex { get; private set; } = 0;
    public bool isAtCheckpoint { get; private set; }  // True when carriage is at a checkpoint (scanning)

    float[] checkpoints;
    int cpIndex;
    int direction = 1;
    float timer;
    float scanPulse;

    Transform carriage;
    float railY, railZ;
    bool isBackRail;

    Camera sensorCam;
    public RenderTexture sensorRT { get; private set; }

    GameObject radarCone;
    Renderer radarRenderer;

    List<float> discoveredCheckpoints = new List<float>();
    float calibrationX;
    float calibStartX, calibEndX;
    bool calibDone;

    ProfessionalLibrary library;
    public int[] zoneIds;

    void Start()
    {
        // Force skip calibration
        skipCalibration = true;

        carriage = transform.Find("Carriage");
        if (carriage == null) { enabled = false; return; }

        library = FindFirstObjectByType<ProfessionalLibrary>();
        if (library == null) { enabled = false; return; }

        railY = carriage.localPosition.y;
        railZ = carriage.localPosition.z;
        isBackRail = transform.name.Contains("Back");

        zoneIds = isBackRail ? new int[] { 1, 2, 3, 4 } : new int[] { 5, 6, 7 };

        SetupCamera();

        SetupRadarCone();

        float usableW = library.roomWidth - 4f;
        calibStartX = -usableW / 2f - 1f;
        calibEndX = usableW / 2f + 1f;
        calibrationX = calibStartX;
        carriage.localPosition = new Vector3(calibStartX, railY, railZ);

        phase = Phase.Calibrating;
        statusText = "CALIBRATING";

        if (skipCalibration)
        {
            calibrationX = calibEndX;
            carriage.localPosition = new Vector3(calibEndX, railY, railZ);
            Debug.Log($"[SENSOR] {transform.name} skipCalibration: pos={carriage.localPosition.x}, calibEndX={calibEndX}");
            FinishCalibration();
        }
    }

    void SetupCamera()
    {
        sensorRT = new RenderTexture(renderSize, renderSize, 16);
        sensorRT.name = $"SensorRT_{transform.name}";

        GameObject camObj = new GameObject("SensorCamera");
        camObj.transform.SetParent(carriage);
        camObj.transform.localPosition = new Vector3(0, -0.21f, 0);
        camObj.transform.localRotation = Quaternion.Euler(90f, 0, 0);

        sensorCam = camObj.AddComponent<Camera>();
        sensorCam.fieldOfView = cameraFOV;
        sensorCam.targetTexture = sensorRT;
        sensorCam.nearClipPlane = 0.1f;
        sensorCam.farClipPlane = 15f;
        sensorCam.clearFlags = CameraClearFlags.SolidColor;
        sensorCam.backgroundColor = new Color(0.1f, 0.1f, 0.12f);
        sensorCam.depth = -10;
        sensorCam.enabled = true;

        var urp = camObj.AddComponent<UnityEngine.Rendering.Universal.UniversalAdditionalCameraData>();
        urp.renderShadows = false;
    }

    void SetupRadarCone()
    {
        radarCone = GameObject.CreatePrimitive(PrimitiveType.Cube);
        radarCone.name = "RadarCone";
        radarCone.transform.SetParent(carriage);
        radarCone.transform.localPosition = new Vector3(0, -1.5f, 0);
        radarCone.transform.localScale = new Vector3(2.5f, 2.8f, 2.5f);
        DestroyImmediate(radarCone.GetComponent<Collider>());

        radarRenderer = radarCone.GetComponent<Renderer>();
        var mat = new Material(radarRenderer.sharedMaterial);
        mat.color = new Color(0.2f, 0.7f, 0.3f, 0.06f);
        mat.SetFloat("_Surface", 1);
        mat.SetOverrideTag("RenderType", "Transparent");
        mat.SetInt("_SrcBlend", (int)UnityEngine.Rendering.BlendMode.SrcAlpha);
        mat.SetInt("_DstBlend", (int)UnityEngine.Rendering.BlendMode.OneMinusSrcAlpha);
        mat.SetInt("_ZWrite", 0);
        mat.EnableKeyword("_SURFACE_TYPE_TRANSPARENT");
        mat.renderQueue = 3000;
        radarRenderer.sharedMaterial = mat;

        radarCone.SetActive(false);
    }

    void Update()
    {
        switch (phase)
        {
            case Phase.Calibrating: DoCalibration(); break;
            case Phase.Scanning: DoScanning(); break;
        }
    }

    void DoCalibration()
    {
        statusText = $"CALIBRATING X={calibrationX:F1}m";

        calibrationX += calibrationSpeed * Time.deltaTime;
        carriage.localPosition = new Vector3(calibrationX, railY, railZ);

        float progress = (calibrationX - calibStartX) / (calibEndX - calibStartX);
        if (Time.frameCount % 30 == 0)
        {
            Vector3 sensorPos = carriage.position + Vector3.down * 0.21f;
            float radarDist = 99f;
            if (Physics.Raycast(sensorPos, Vector3.down, out RaycastHit hit, 15f))
                radarDist = hit.distance;

            Debug.Log($"[SENSOR→PI] {transform.name} calibration sweep | " +
                $"X={calibrationX:F2}m | progress={progress * 100:F0}% | " +
                $"radar_dist={radarDist:F2}m | camera_frame=captured | " +
                $"sending to RPi for object recognition...");
        }

        if (calibrationX >= calibEndX)
        {
            FinishCalibration();
        }
    }

    void FinishCalibration()
    {

        float usableW = library.roomWidth - 4f;
        float colSpacing = usableW / 4f;
        float startX = -usableW / 2f + colSpacing / 2f;
        int count = isBackRail ? 4 : 3;
        checkpoints = new float[count];

        Debug.Log($"[PI→SENSOR] {transform.name} - RPi completed analysis. " +
            $"Identified {count} seat clusters via object recognition + radar mapping.");

        for (int i = 0; i < count; i++)
        {
            checkpoints[i] = startX + i * colSpacing;

            GameObject marker = GameObject.CreatePrimitive(PrimitiveType.Cube);
            marker.name = $"Checkpoint_{i}";
            marker.transform.SetParent(transform);
            marker.transform.position = new Vector3(
                checkpoints[i],
                carriage.position.y - 0.04f,
                carriage.position.z);
            marker.transform.localScale = new Vector3(0.08f, 0.008f, 0.08f);
            var rn = marker.GetComponent<Renderer>();
            var m = new Material(rn.sharedMaterial);
            m.color = new Color(0.1f, 0.9f, 0.3f);
            rn.sharedMaterial = m;
            DestroyImmediate(marker.GetComponent<Collider>());

            Debug.Log($"[PI→SENSOR] {transform.name} - Checkpoint {i}: X={checkpoints[i]:F1}m " +
                $"(Zone {zoneIds[Mathf.Min(i, zoneIds.Length - 1)]})");
        }

        cpIndex = 0;
        isAtCheckpoint = false;
        timer = 0;
        phase = Phase.Scanning;
        statusText = "SCANNING";

        Debug.Log($"[SENSOR] {transform.name} calibration complete. Switching to scan mode.");
    }

    void DoScanning()
    {
        if (checkpoints == null || checkpoints.Length == 0) return;

        if (isAtCheckpoint)
        {
            timer += Time.deltaTime;
            radarCone.SetActive(true);

            scanPulse += Time.deltaTime * 4f;
            float alpha = 0.04f + Mathf.Sin(scanPulse) * 0.03f;
            Color c = DetectPresence() ?
                new Color(0.8f, 0.2f, 0.2f, alpha) :
                new Color(0.2f, 0.7f, 0.3f, alpha);
            radarRenderer.material.color = c;

            int zoneIdx = Mathf.Clamp(cpIndex, 0, zoneIds.Length - 1);
            currentZoneIndex = zoneIdx;
            statusText = $"SCANNING Zone {zoneIds[zoneIdx]}";

            if (timer >= scanDuration)
            {
                OutputTelemetry(zoneIds[zoneIdx]);
                radarCone.SetActive(false);
                isAtCheckpoint = false;
                timer = 0;

                cpIndex += direction;
                if (cpIndex >= checkpoints.Length) { direction = -1; cpIndex = checkpoints.Length - 2; }
                else if (cpIndex < 0) { direction = 1; cpIndex = 1; }

                statusText = "MOVING";
            }
        }
        else
        {
            float targetX = checkpoints[Mathf.Clamp(cpIndex, 0, checkpoints.Length - 1)];
            float currentX = carriage.localPosition.x;
            float diff = targetX - currentX;

            if (Mathf.Abs(diff) > 0.05f)
            {
                float move = Mathf.Sign(diff) * moveSpeed * Time.deltaTime;
                if (Mathf.Abs(move) > Mathf.Abs(diff)) move = diff;
                carriage.localPosition = new Vector3(currentX + move, railY, railZ);
            }
            else
            {
                carriage.localPosition = new Vector3(targetX, railY, railZ);
                isAtCheckpoint = true;
                timer = 0;
                scanPulse = 0;
            }
        }
    }

    bool DetectPresence()
    {
        if (checkpoints == null || cpIndex < 0 || cpIndex >= zoneIds.Length) return false;
        int zoneId = zoneIds[Mathf.Clamp(cpIndex, 0, zoneIds.Length - 1)];
        var seats = library.GetSeatsInZone(zoneId);

        var students = FindObjectsByType<SimStudent>(FindObjectsSortMode.None);
        foreach (var st in students)
        {
            if (st.state == SimStudent.S.DONE) continue;
            foreach (var seat in seats)
            {
                if (st.assignedSeatId == seat.seatId &&
                    st.state != SimStudent.S.WALK_OUT &&
                    st.state != SimStudent.S.SPAWN)
                    return true;
            }
        }

        foreach (var seat in seats)
        {
            if (seat.seatTransform == null) continue;
            var chair = seat.seatTransform.Find("Chair");
            if (chair == null) continue;
            foreach (var bag in FindObjectsByType<Transform>(FindObjectsSortMode.None))
            {
                if (bag.name == "Bag" && bag.parent == null)
                {
                    if (Vector3.Distance(bag.position, chair.position) < 1f)
                        return true;
                }
            }
        }

        return false;
    }

    void OutputTelemetry(int zoneId)
    {
        var seats = library.GetSeatsInZone(zoneId);
        var students = FindObjectsByType<SimStudent>(FindObjectsSortMode.None);

        string timestamp = System.DateTimeOffset.UtcNow.ToUnixTimeSeconds().ToString();
        string seatData = "";

        foreach (var seat in seats)
        {
            string objectType = "empty";
            float presence = 0f;
            float motion = 0f;
            float confidence = 0f;
            bool microMotion = false;

            foreach (var st in students)
            {
                if (st.assignedSeatId != seat.seatId) continue;

                switch (st.state)
                {
                    case SimStudent.S.STUDY:
                    case SimStudent.S.STUDY2:
                    case SimStudent.S.SIT:
                    case SimStudent.S.SIT2:
                    case SimStudent.S.PLACE:
                        objectType = "person";
                        presence = 0.85f + Random.Range(-0.1f, 0.1f);
                        motion = 0.15f + Random.Range(-0.1f, 0.1f);
                        confidence = 0.90f + Random.Range(-0.05f, 0.05f);
                        microMotion = true;
                        break;

                    case SimStudent.S.WALK_TO_COOLER:
                    case SimStudent.S.DRINK:
                    case SimStudent.S.WALK_BACK:
                        if (st.willGhostLeave || true)
                        {
                            objectType = "bag";
                            presence = 0.45f + Random.Range(-0.15f, 0.15f);
                            motion = 0.02f + Random.Range(0f, 0.03f);
                            confidence = 0.75f + Random.Range(-0.1f, 0.1f);
                            microMotion = false;
                        }
                        break;

                    case SimStudent.S.PACK:
                    case SimStudent.S.STAND:
                    case SimStudent.S.STAND2:
                        objectType = "person";
                        presence = 0.70f + Random.Range(-0.15f, 0.15f);
                        motion = 0.60f + Random.Range(-0.2f, 0.2f);
                        confidence = 0.80f + Random.Range(-0.1f, 0.1f);
                        microMotion = true;
                        break;
                }
                break;
            }

            presence = Mathf.Clamp01(presence);
            motion = Mathf.Clamp01(motion);
            confidence = Mathf.Clamp01(confidence);

            if (seatData.Length > 0) seatData += ",\n      ";
            seatData += $"\"{seat.seatId}\": {{ " +
                $"\"presence\": {presence:F2}, \"motion\": {motion:F2}, " +
                $"\"object_type\": \"{objectType}\", \"confidence\": {confidence:F2}, " +
                $"\"micro_motion\": {(microMotion ? "true" : "false")} }}";
        }

        string json = $@"{{
  ""timestamp"": {timestamp},
  ""zone_id"": ""Z{zoneId}"",
  ""sensor"": ""{transform.name}"",
  ""seats"": {{
      {seatData}
  }}
}}";

        Debug.Log($"[TELEMETRY] {transform.name} Zone {zoneId}:\n{json}");

        // Telemetry now handled by YoloCapture for training data
        // and DashboardBridge for live inference
    }
}
