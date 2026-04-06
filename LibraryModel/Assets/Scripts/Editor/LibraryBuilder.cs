using UnityEngine;
using UnityEditor;

public class LibraryBuilder
{
    [MenuItem("Liberty Twin/Build Library")]
    public static void BuildLibrary()
    {
        var lib = Object.FindFirstObjectByType<ProfessionalLibrary>();
        if (lib != null)
        {
            lib.BuildLibrary();
            EditorUtility.SetDirty(lib.gameObject);
            Debug.Log("[Liberty Twin] Library built successfully.");
        }
        else
            Debug.LogError("[Liberty Twin] No ProfessionalLibrary found in scene.");
    }

    [MenuItem("Liberty Twin/Start Crowd Sim")]
    public static void StartCrowdSim()
    {
        ClearCrowd();

        GameObject go = new GameObject("SimManager");
        go.AddComponent(System.Type.GetType("LibrarySimManager, Assembly-CSharp"));

        go.AddComponent(System.Type.GetType("DashboardBridge, Assembly-CSharp"));

        EditorUtility.SetDirty(go);
        Selection.activeGameObject = go;
        Debug.Log("[Liberty Twin] Crowd Sim + Dashboard Bridge created. " +
            "Run 'python dashboard/server.py' then open http://localhost:5000");
    }

    [MenuItem("Liberty Twin/Clear Crowd")]
    public static void ClearCrowd()
    {
        var mgr = GameObject.Find("SimManager");
        if (mgr != null) Object.DestroyImmediate(mgr);

        foreach (var go in Object.FindObjectsByType<GameObject>(FindObjectsSortMode.None))
        {
            if (go.name.StartsWith("Student")) Object.DestroyImmediate(go);
        }

        var old = GameObject.Find("Student");
        if (old != null) Object.DestroyImmediate(old);

        Debug.Log("[Liberty Twin] Crowd cleared.");
    }
}
