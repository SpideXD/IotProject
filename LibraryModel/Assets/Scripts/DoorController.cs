using UnityEngine;

public class DoorController : MonoBehaviour
{
    public float openDistance = 3.0f;
    public float openSpeed = 2.0f;
    public float openAngle = 90.0f;

    private Transform player;
    private Quaternion closedRotation;
    private Quaternion openRotation;
    private bool isOpen = false;

    void Start()
    {
        GameObject p = GameObject.FindGameObjectWithTag("Player");
        if (p == null) p = GameObject.Find("Player");

        if (p != null) player = p.transform;

        closedRotation = transform.localRotation;
        openRotation = Quaternion.Euler(0, openAngle, 0) * closedRotation;
    }

    void Update()
    {
        if (player == null) return;

        float distance = Vector3.Distance(transform.position, player.position);

        if (distance <= openDistance)
        {
            isOpen = true;
        }
        else if (distance > openDistance * 1.2f)
        {
            isOpen = false;
        }

        Quaternion targetRotation = isOpen ? openRotation : closedRotation;
        transform.localRotation = Quaternion.Slerp(transform.localRotation, targetRotation, Time.deltaTime * openSpeed);
    }
}
