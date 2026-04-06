using UnityEngine;
using UnityEngine.UI;

public class SensorFeedUI : MonoBehaviour
{
    RailSensorController backSensor, frontSensor;
    RawImage backFeed, frontFeed;
    Text backLabel, frontLabel, backStatus, frontStatus;

    void Start()
    {
        var sensors = FindObjectsByType<RailSensorController>(FindObjectsSortMode.None);
        foreach (var s in sensors)
        {
            if (s.transform.name.Contains("Back")) backSensor = s;
            else frontSensor = s;
        }

        BuildMonitorDisplay();
    }

    void BuildMonitorDisplay()
    {
        var lib = FindFirstObjectByType<ProfessionalLibrary>();
        if (lib == null) return;

        float halfW = lib.roomWidth / 2f;
        float halfL = lib.roomLength / 2f;

        Vector3 monitorPos = new Vector3(-halfW + 7.0f, 1.9f, halfL - 0.18f);

        GameObject canvasObj = new GameObject("SensorMonitor");
        canvasObj.transform.SetParent(transform);
        canvasObj.transform.position = monitorPos;
        canvasObj.transform.rotation = Quaternion.identity;

        Canvas canvas = canvasObj.AddComponent<Canvas>();
        canvas.renderMode = RenderMode.WorldSpace;

        RectTransform crt = canvasObj.GetComponent<RectTransform>();
        crt.sizeDelta = new Vector2(800, 500);
        crt.localScale = new Vector3(-0.002f, 0.002f, 0.002f);

        canvasObj.AddComponent<CanvasScaler>();

        GameObject bg = CreateUIPanel(canvasObj, "Background",
            new Vector2(0, 0), new Vector2(800, 500),
            new Color(0.08f, 0.08f, 0.10f));

        CreateUIPanel(canvasObj, "Bezel_T", new Vector2(0, 245), new Vector2(800, 10), new Color(0.15f, 0.15f, 0.18f));
        CreateUIPanel(canvasObj, "Bezel_B", new Vector2(0, -245), new Vector2(800, 10), new Color(0.15f, 0.15f, 0.18f));
        CreateUIPanel(canvasObj, "Bezel_L", new Vector2(-395, 0), new Vector2(10, 500), new Color(0.15f, 0.15f, 0.18f));
        CreateUIPanel(canvasObj, "Bezel_R", new Vector2(395, 0), new Vector2(10, 500), new Color(0.15f, 0.15f, 0.18f));

        CreateUIText(canvasObj, "Title", new Vector2(0, 220),
            "LIBERTY TWIN - SENSOR MONITORING SYSTEM", 18, Color.white);

        CreateUIPanel(canvasObj, "Divider", new Vector2(0, 200), new Vector2(760, 2), new Color(0.3f, 0.3f, 0.35f));

        CreateUIText(canvasObj, "BackTitle", new Vector2(-200, 185),
            "SENSOR 1 - BACK ROW (Zones 1-4)", 12, new Color(0.7f, 0.9f, 0.7f));

        GameObject backFeedObj = new GameObject("BackFeed");
        backFeedObj.transform.SetParent(canvasObj.transform, false);
        RectTransform bfrt = backFeedObj.AddComponent<RectTransform>();
        bfrt.anchoredPosition = new Vector2(-200, 30);
        bfrt.sizeDelta = new Vector2(340, 280);
        backFeed = backFeedObj.AddComponent<RawImage>();
        backFeed.color = Color.white;
        if (backSensor != null && backSensor.sensorRT != null)
            backFeed.texture = backSensor.sensorRT;

        backLabel = CreateUIText(canvasObj, "BackLabel", new Vector2(-200, -130),
            "Zone: --", 14, new Color(0.9f, 0.9f, 0.3f)).GetComponent<Text>();
        backStatus = CreateUIText(canvasObj, "BackStatus", new Vector2(-200, -155),
            "Status: INIT", 12, new Color(0.5f, 0.8f, 0.5f)).GetComponent<Text>();

        CreateUIText(canvasObj, "FrontTitle", new Vector2(200, 185),
            "SENSOR 2 - FRONT ROW (Zones 5-7)", 12, new Color(0.7f, 0.9f, 0.7f));

        GameObject frontFeedObj = new GameObject("FrontFeed");
        frontFeedObj.transform.SetParent(canvasObj.transform, false);
        RectTransform ffrt = frontFeedObj.AddComponent<RectTransform>();
        ffrt.anchoredPosition = new Vector2(200, 30);
        ffrt.sizeDelta = new Vector2(340, 280);
        frontFeed = frontFeedObj.AddComponent<RawImage>();
        frontFeed.color = Color.white;
        if (frontSensor != null && frontSensor.sensorRT != null)
            frontFeed.texture = frontSensor.sensorRT;

        frontLabel = CreateUIText(canvasObj, "FrontLabel", new Vector2(200, -130),
            "Zone: --", 14, new Color(0.9f, 0.9f, 0.3f)).GetComponent<Text>();
        frontStatus = CreateUIText(canvasObj, "FrontStatus", new Vector2(200, -155),
            "Status: INIT", 12, new Color(0.5f, 0.8f, 0.5f)).GetComponent<Text>();

        CreateUIPanel(canvasObj, "CenterDiv", new Vector2(0, 30), new Vector2(2, 300), new Color(0.3f, 0.3f, 0.35f));

        CreateUIPanel(canvasObj, "BottomBar", new Vector2(0, -195), new Vector2(760, 30), new Color(0.12f, 0.12f, 0.15f));
        CreateUIText(canvasObj, "BottomText", new Vector2(0, -195),
            "Liberty Twin IoT Monitoring  |  Camera + Radar  |  Auto-Calibrated", 10,
            new Color(0.5f, 0.5f, 0.55f));

        GameObject frame = GameObject.CreatePrimitive(PrimitiveType.Cube);
        frame.name = "MonitorFrame";
        frame.transform.SetParent(transform);
        frame.transform.position = monitorPos + new Vector3(0, 0, 0.04f);
        frame.transform.localScale = new Vector3(1.65f, 1.05f, 0.06f);
        var rn = frame.GetComponent<Renderer>();
        var mat = new Material(rn.sharedMaterial);
        mat.color = new Color(0.12f, 0.12f, 0.15f);
        rn.sharedMaterial = mat;
        DestroyImmediate(frame.GetComponent<Collider>());
    }

    void Update()
    {
        if (backSensor == null || frontSensor == null)
        {
            var sensors = FindObjectsByType<RailSensorController>(FindObjectsSortMode.None);
            foreach (var s in sensors)
            {
                if (s.transform.name.Contains("Back")) backSensor = s;
                else frontSensor = s;
            }
        }

        if (backSensor != null && backLabel != null)
        {
            int zi = backSensor.currentZoneIndex;
            int[] zones = { 1, 2, 3, 4 };
            int z = zi >= 0 && zi < zones.Length ? zones[zi] : 0;
            backLabel.text = $"Zone: {z}";
            backStatus.text = $"Status: {backSensor.statusText}";
            backStatus.color = backSensor.phase == RailSensorController.Phase.Calibrating ?
                new Color(0.9f, 0.7f, 0.2f) : new Color(0.5f, 0.8f, 0.5f);

            if (backFeed.texture == null && backSensor.sensorRT != null)
                backFeed.texture = backSensor.sensorRT;
        }

        if (frontSensor != null && frontLabel != null)
        {
            int zi = frontSensor.currentZoneIndex;
            int[] zones = { 5, 6, 7 };
            int z = zi >= 0 && zi < zones.Length ? zones[zi] : 0;
            frontLabel.text = $"Zone: {z}";
            frontStatus.text = $"Status: {frontSensor.statusText}";
            frontStatus.color = frontSensor.phase == RailSensorController.Phase.Calibrating ?
                new Color(0.9f, 0.7f, 0.2f) : new Color(0.5f, 0.8f, 0.5f);

            if (frontFeed.texture == null && frontSensor.sensorRT != null)
                frontFeed.texture = frontSensor.sensorRT;
        }
    }

    GameObject CreateUIPanel(GameObject parent, string name, Vector2 pos, Vector2 size, Color color)
    {
        GameObject obj = new GameObject(name);
        obj.transform.SetParent(parent.transform, false);
        RectTransform rt = obj.AddComponent<RectTransform>();
        rt.anchoredPosition = pos;
        rt.sizeDelta = size;
        Image img = obj.AddComponent<Image>();
        img.color = color;
        return obj;
    }

    GameObject CreateUIText(GameObject parent, string name, Vector2 pos, string content,
        int fontSize, Color color)
    {
        GameObject obj = new GameObject(name);
        obj.transform.SetParent(parent.transform, false);
        RectTransform rt = obj.AddComponent<RectTransform>();
        rt.anchoredPosition = pos;
        rt.sizeDelta = new Vector2(380, 30);
        Text txt = obj.AddComponent<Text>();
        txt.text = content;
        txt.fontSize = fontSize;
        txt.color = color;
        txt.alignment = TextAnchor.MiddleCenter;
        txt.font = Resources.GetBuiltinResource<Font>("LegacyRuntime.ttf");
        return obj;
    }
}
