using UnityEngine;
using System.Collections.Generic;

public class SimStudent : MonoBehaviour
{
    [HideInInspector] public string assignedSeatId;
    [HideInInspector] public float walkSpeed = 1.8f;
    [HideInInspector] public float studyDuration = 45f;
    [HideInInspector] public float secondStudyDuration = 25f;
    [HideInInspector] public bool willTakeWaterBreak;
    [HideInInspector] public bool willGhostLeave;
    [HideInInspector] public Color shirtColor, pantsColor, skinColor, hairColor;
    [HideInInspector] public Color bagColor, shoeColor;
    [HideInInspector] public bool hasGlasses;
    [HideInInspector] public float bodyScale = 1f;

    public enum S {
        SPAWN, WALK_TO_SEAT, SIT, PLACE, STUDY,
        USE_PHONE, PUT_AWAY_PHONE,
        STAND, WALK_TO_COOLER, DRINK, WALK_BACK,
        SIT2, STUDY2, PACK, STAND2, WALK_OUT, DONE,
        STRETCH, YAW, TALK
    }
    public S state { get; private set; } = S.SPAWN;

    // New timing fields
    float phoneTimer, stretchTimer, yawnTimer, talkTimer;
    float lastPhoneUse, lastStretch, lastYawn;
    float stretchInterval = 25f; // Average between stretches
    float phoneUseInterval = 45f; // Average between phone uses

    // Micro-behavior data
    float typingTimer;
    float legBouncePhase;
    float headBobPhase;

    // Reference to sim time manager
    SimulationTimeManager simTime => FindFirstObjectByType<SimulationTimeManager>();

    // Semester mode influence
    bool IsStressMode()
    {
        if (simTime == null) return false;
        return simTime.semesterMode == SimulationTimeManager.SemesterMode.DeadWeek ||
               simTime.semesterMode == SimulationTimeManager.SemesterMode.FinalsWeek;
    }

    LibrarySimManager mgr;
    ProfessionalLibrary lib;
    List<Vector3> wp = new List<Vector3>();
    int wpi;
    Vector3 chairP, deskP, standP, seatP;
    float cSide, timer, wCycle;
    GameObject body, bagO, lapO, bookO, cupO, headPhO;
    Transform lL, lR;
    Transform kL, kR;
    bool placed;
    bool hasHeadphones;
    bool hasCoffee;

    public void Init(LibrarySimManager m, ProfessionalLibrary l)
    {
        mgr = m; lib = l;
        if (!FindSeat()) { state = S.DONE; return; }
        BuildModel();
        PathToSeat();
        state = S.SPAWN; timer = 0;
    }

    bool FindSeat()
    {
        var s = lib.GetSeatById(assignedSeatId);
        if (s == null) return false;
        var ch = s.seatTransform.Find("Chair");
        var dk = s.seatTransform.Find("DeskTop");
        if (ch == null || dk == null) return false;
        chairP = ch.position;
        deskP = dk.position + Vector3.up * 0.04f;
        cSide = (ch.position.z > dk.position.z) ? 1f : -1f;
        return true;
    }

    void PathToSeat()
    {
        wp.Clear(); wpi = 0;
        float hL = lib.roomLength / 2f;
        wp.Add(new Vector3(0, 0, hL - 1.5f));
        wp.Add(new Vector3(0, 0, chairP.z));
        wp.Add(new Vector3(chairP.x, 0, chairP.z));
    }
    void PathToCooler()
    {
        wp.Clear(); wpi = 0;
        var c = mgr.waterCoolerPos;
        wp.Add(new Vector3(0, 0, chairP.z));
        wp.Add(new Vector3(0, 0, c.z));
        wp.Add(c + new Vector3(Random.Range(-0.3f, 0.3f), 0, 0.4f));
    }
    void PathBack()
    {
        wp.Clear(); wpi = 0;
        var c = mgr.waterCoolerPos;
        wp.Add(new Vector3(0, 0, c.z));
        wp.Add(new Vector3(0, 0, chairP.z));
        wp.Add(new Vector3(chairP.x, 0, chairP.z));
    }
    void PathOut()
    {
        wp.Clear(); wpi = 0;
        float hL = lib.roomLength / 2f;
        wp.Add(new Vector3(0, 0, chairP.z));
        wp.Add(new Vector3(0, 0, hL - 1f));
        wp.Add(new Vector3(0, 0, hL + 2f));
    }

    void Update()
    {
        timer += Time.deltaTime;
        UpdateMicroBehaviors();

        switch (state)
        {
            case S.SPAWN: if (timer > 0.3f) { state = S.WALK_TO_SEAT; timer = 0; } break;
            case S.WALK_TO_SEAT: case S.WALK_TO_COOLER: case S.WALK_BACK: case S.WALK_OUT:
                Walk(); break;
            case S.SIT: case S.SIT2: Sit(); break;
            case S.PLACE: Place(); break;

            case S.STUDY:
                // Check for phone use
                lastPhoneUse += Time.deltaTime;
                if (lastPhoneUse > phoneUseInterval && Random.value < 0.02f)
                {
                    state = S.USE_PHONE;
                    phoneTimer = 0;
                    timer = 0;
                    break;
                }
                // Check for yawn
                lastYawn += Time.deltaTime;
                if (lastYawn > 20f && Random.value < 0.03f)
                {
                    Yawn();
                    lastYawn = 0;
                }
                // Check for stretch
                lastStretch += Time.deltaTime;
                if (lastStretch > stretchInterval && Random.value < 0.05f)
                {
                    state = S.STRETCH;
                    stretchTimer = 0;
                    timer = 0;
                    break;
                }
                // Stress mode: faster study
                float studyMult = IsStressMode() ? 0.85f : 1f;
                if (timer >= studyDuration * studyMult) { timer = 0; state = willTakeWaterBreak ? S.STAND : S.PACK; }
                break;

            case S.STUDY2:
                // Same behaviors for second study period
                lastPhoneUse += Time.deltaTime;
                if (lastPhoneUse > phoneUseInterval * 0.7f && Random.value < 0.025f)
                {
                    state = S.USE_PHONE;
                    phoneTimer = 0;
                    timer = 0;
                    break;
                }
                lastStretch += Time.deltaTime;
                if (lastStretch > stretchInterval * 0.8f && Random.value < 0.04f)
                {
                    state = S.STRETCH;
                    stretchTimer = 0;
                    timer = 0;
                    break;
                }
                float study2Mult = IsStressMode() ? 0.80f : 1f;
                if (timer >= secondStudyDuration * study2Mult) { timer = 0; state = S.PACK; }
                break;

            case S.USE_PHONE:
                PhoneUse();
                break;
            case S.PUT_AWAY_PHONE:
                PutAwayPhone();
                break;

            case S.STRETCH:
                DoStretch();
                break;

            case S.YAW:
                DoYawn();
                break;

            case S.TALK:
                DoTalk();
                break;

            case S.STAND: case S.STAND2: Stand(); break;
            case S.DRINK: if (timer >= 4f) { timer = 0; PathBack(); state = S.WALK_BACK; } break;
            case S.PACK: Pack(); break;
        }
    }

    void UpdateMicroBehaviors()
    {
        // Leg bounce during sitting (subtle animation)
        if (state == S.STUDY || state == S.STUDY2 || state == S.SIT || state == S.SIT2 || state == S.PLACE)
        {
            legBouncePhase += Time.deltaTime * 0.8f;
            float bounce = Mathf.Sin(legBouncePhase) * 0.005f;
            if (lL) lL.localPosition = new Vector3(-0.08f, 0.82f + bounce, 0);
            if (lR) lR.localPosition = new Vector3(0.08f, 0.82f + bounce, 0);
        }

        // Head bob when tired (stress mode) - subtle forward tilt
        if ((state == S.STUDY || state == S.STUDY2) && IsStressMode())
        {
            headBobPhase += Time.deltaTime * 0.5f;
            float headTilt = Mathf.Sin(headBobPhase) * 2f;
            Transform head = body.transform.Find("Head");
            if (head != null)
            {
                head.localRotation = Quaternion.Euler(headTilt, 0, 0);
            }
        }

        // Typing animation when laptop is open - hands move slightly
        if ((state == S.STUDY || state == S.STUDY2) && lapO != null && lapO.transform.parent != body.transform)
        {
            typingTimer += Time.deltaTime;
            // Subtle hand movement while typing
            float typePhase = typingTimer * 8f;
            Transform handR = body.transform.Find("HandR");
            if (handR != null)
            {
                float typeOffset = Mathf.Sin(typePhase) * 0.01f;
                handR.localPosition = new Vector3(0.22f, 0.78f + typeOffset, 0);
            }
        }

        // Arm rest when not typing
        if ((state == S.STUDY || state == S.STUDY2) && lapO != null && lapO.transform.parent != body.transform)
        {
            // Arms relaxed on desk
            Transform armR = body.transform.Find("ArmR");
            if (armR != null)
            {
                armR.localRotation = Quaternion.Lerp(armR.localRotation, Quaternion.Euler(0, 0, -15f), Time.deltaTime * 2f);
            }
        }
    }

    void Yawn()
    {
        // Micro-behavior: just yawn, doesn't change state
        Debug.Log($"[Student] {name} yawns");
        // Could trigger head tilt animation here
    }

    void DoYawn()
    {
        // Quick yawn animation (0.8s)
        if (timer >= 0.8f)
        {
            state = S.STUDY;
            timer = 0;
        }
    }

    void PhoneUse()
    {
        phoneTimer += Time.deltaTime;
        // Pull phone out, look down
        // During this time, student is distracted
        if (phoneTimer >= 15f + Random.Range(-5f, 10f))
        {
            state = S.PUT_AWAY_PHONE;
            timer = 0;
            phoneTimer = 0;
        }
    }

    void PutAwayPhone()
    {
        timer += Time.deltaTime;
        if (timer >= 3f)
        {
            state = S.STUDY;
            timer = 0;
            lastPhoneUse = 0; // Reset timer
        }
    }

    void DoStretch()
    {
        stretchTimer += Time.deltaTime;
        if (stretchTimer >= 4f + Random.Range(-1f, 2f))
        {
            state = S.STUDY;
            timer = 0;
            lastStretch = 0;
        }
    }

    void DoTalk()
    {
        talkTimer += Time.deltaTime;
        if (talkTimer >= 10f + Random.Range(-5f, 10f))
        {
            // Finish talking and return to study
            state = S.STUDY;
            timer = 0;
        }
    }

    void Walk()
    {
        if (wpi >= wp.Count) { WalkDone(); return; }
        Vector3 t = wp[wpi]; t.y = 0;
        Vector3 me = transform.position; me.y = 0;
        Vector3 d = t - me;
        if (d.magnitude > 0.15f)
        {
            Vector3 dir = d.normalized;
            transform.position += dir * walkSpeed * Time.deltaTime;
            transform.position = new Vector3(transform.position.x, 0, transform.position.z);
            if (dir.sqrMagnitude > 0.001f)
                transform.rotation = Quaternion.Slerp(transform.rotation, Quaternion.LookRotation(dir), Time.deltaTime * 8f);
            Legs(true);
        }
        else { transform.position = new Vector3(t.x, 0, t.z); wpi++; }
    }

    void WalkDone()
    {
        Legs(false); timer = 0;
        switch (state)
        {
            case S.WALK_TO_SEAT: PrepSit(); state = S.SIT; break;
            case S.WALK_TO_COOLER:
                var dir = (mgr.waterCoolerPos - transform.position);
                dir.y = 0;
                if (dir.sqrMagnitude > 0.01f) transform.rotation = Quaternion.LookRotation(dir.normalized);
                state = S.DRINK; break;
            case S.WALK_BACK: PrepSit(); state = S.SIT2; break;
            case S.WALK_OUT: state = S.DONE; break;
        }
    }

    void PrepSit()
    {
        transform.rotation = Quaternion.LookRotation(new Vector3(0, 0, -cSide));
        standP = new Vector3(chairP.x, 0, chairP.z);
        float seatY = Mathf.Max(chairP.y + 0.45f - 0.83f, -0.35f);
        seatP = new Vector3(chairP.x, seatY, chairP.z - cSide * 0.08f);
    }

    void Sit()
    {
        // Improved easing with slight overshoot for natural feel
        float rawT = Mathf.Clamp01(timer / 0.6f);
        float t = EaseOutBack(rawT);

        // Position interpolation
        transform.position = Vector3.Lerp(standP, seatP, t);

        // Upper body slight forward lean during sit (natural posture)
        float leanAngle = Mathf.Sin(rawT * Mathf.PI) * 8f;
        body.transform.localRotation = Quaternion.Euler(leanAngle, 0, 0);

        // Legs bend smoothly
        if (lL && lR)
        {
            lL.localRotation = Quaternion.Euler(-t * 85, 0, 0);
            lR.localRotation = Quaternion.Euler(-t * 85, 0, 0);
        }
        if (kL && kR)
        {
            kL.localRotation = Quaternion.Euler(t * 85, 0, 0);
            kR.localRotation = Quaternion.Euler(t * 85, 0, 0);
        }

        if (rawT >= 1f)
        {
            body.transform.localRotation = Quaternion.identity; // Reset lean
            timer = 0;
            if (state == S.SIT && !placed) state = S.PLACE;
            else if (state == S.SIT) state = S.STUDY;
            else state = S.STUDY2;
        }
    }

    // EaseOutBack: slight overshoot for natural feel
    float EaseOutBack(float x)
    {
        float c1 = 1.70158f;
        float c3 = c1 + 1;
        return 1 + c3 * Mathf.Pow(x - 1, 3) + c1 * Mathf.Pow(x - 1, 2);
    }

    // EaseInOutCubic for smooth transitions
    float EaseInOutCubic(float x)
    {
        return x < 0.5f ? 4 * x * x * x : 1 - Mathf.Pow(-2 * x + 2, 3) / 2;
    }

    void Stand()
    {
        float rawT = Mathf.Clamp01(timer / 0.5f);
        float t = EaseInOutCubic(rawT);

        transform.position = Vector3.Lerp(seatP, standP, t);

        // Upper body slight forward lean when rising
        float leanAngle = Mathf.Sin((1 - rawT) * Mathf.PI) * 5f;
        body.transform.localRotation = Quaternion.Euler(leanAngle, 0, 0);

        if (lL && lR)
        {
            lL.localRotation = Quaternion.Euler(-(1 - t) * 85, 0, 0);
            lR.localRotation = Quaternion.Euler(-(1 - t) * 85, 0, 0);
        }
        if (kL && kR)
        {
            kL.localRotation = Quaternion.Euler((1 - t) * 85, 0, 0);
            kR.localRotation = Quaternion.Euler((1 - t) * 85, 0, 0);
        }
        if (rawT >= 1f)
        {
            body.transform.localRotation = Quaternion.identity;
            Legs(false); timer = 0;
            if (state == S.STAND) { PathToCooler(); state = S.WALK_TO_COOLER; }
            else { PathOut(); state = S.WALK_OUT; }
        }
    }

    void Place()
    {
        float y = transform.eulerAngles.y;
        if (timer > 0.3f && bagO.transform.parent == body.transform)
        {
            bagO.transform.SetParent(null);
            bagO.transform.position = new Vector3(chairP.x + transform.right.x * 0.45f, 0.15f, chairP.z + transform.right.z * 0.45f);
            bagO.transform.rotation = Quaternion.Euler(0, y + 180f + 15f, 5f);
        }
        if (timer > 0.8f && lapO.transform.parent == body.transform)
        {
            lapO.transform.SetParent(null);
            lapO.transform.position = deskP + transform.forward * 0.05f;
            lapO.transform.rotation = Quaternion.Euler(0, y + 180f, 0);
        }
        if (timer > 1.3f && bookO.transform.parent == body.transform)
        {
            bookO.transform.SetParent(null);
            bookO.transform.position = deskP + transform.forward * 0.05f + transform.right * 0.24f;
            bookO.transform.rotation = Quaternion.Euler(0, y + 180f - 8f, 0);
            placed = true; state = S.STUDY; timer = 0;
        }
    }

    void Pack()
    {
        if (willGhostLeave)
        {
            if (timer > 0.3f && lapO != null && lapO.transform.parent != body.transform)
            {
                lapO.transform.SetParent(body.transform);
                lapO.transform.localPosition = V(0, 0.95f, -0.22f);
                lapO.transform.localRotation = Quaternion.identity;
            }
            if (timer > 0.5f && bagO != null && bagO.transform.parent != body.transform)
            {
                bagO.transform.position = new Vector3(chairP.x, 0.48f, chairP.z);
                bagO.transform.rotation = Quaternion.Euler(0, transform.eulerAngles.y + 180f, 0);
            }
            if (timer > 1.0f) { timer = 0; state = S.STAND2; }
        }
        else
        {
            if (timer > 0.3f && lapO != null && lapO.transform.parent != body.transform)
            {
                lapO.transform.SetParent(body.transform);
                lapO.transform.localPosition = V(0, 0.95f, -0.22f);
                lapO.transform.localRotation = Quaternion.identity;
            }
            if (timer > 0.6f && bookO != null && bookO.transform.parent != body.transform)
            {
                bookO.transform.SetParent(body.transform);
                bookO.transform.localPosition = V(0.25f, 0.90f, 0.08f);
                bookO.transform.localRotation = Quaternion.identity;
            }
            if (timer > 0.9f && bagO != null && bagO.transform.parent != body.transform)
            {
                bagO.transform.SetParent(body.transform);
                bagO.transform.localPosition = V(0, 0.95f, -0.18f);
                bagO.transform.localRotation = Quaternion.identity;
            }
            if (timer > 1.2f) { timer = 0; state = S.STAND2; }
        }
    }

    void Legs(bool walk)
    {
        if (!lL) return;
        if (walk)
        {
            wCycle += Time.deltaTime * 8;
            float s = Mathf.Sin(wCycle) * 25;
            lL.localRotation = Quaternion.Euler(s, 0, 0);
            lR.localRotation = Quaternion.Euler(-s, 0, 0);
            if (kL && kR)
            {
                float kBend = Mathf.Max(0, -Mathf.Sin(wCycle)) * 30;
                float kBend2 = Mathf.Max(0, Mathf.Sin(wCycle)) * 30;
                kL.localRotation = Quaternion.Euler(-kBend, 0, 0);
                kR.localRotation = Quaternion.Euler(-kBend2, 0, 0);
            }
        }
        else
        {
            lL.localRotation = Quaternion.identity;
            lR.localRotation = Quaternion.identity;
            if (kL) kL.localRotation = Quaternion.identity;
            if (kR) kR.localRotation = Quaternion.identity;
        }
    }

    void OnDestroy()
    {
        if (willGhostLeave) return;
        if (bagO && bagO.transform.parent != body?.transform) Destroy(bagO);
        if (lapO && lapO.transform.parent != body?.transform) Destroy(lapO);
        if (bookO && bookO.transform.parent != body?.transform) Destroy(bookO);
        if (cupO && cupO.transform.parent != body?.transform) Destroy(cupO);
        if (headPhO && headPhO.transform.parent != body?.transform) Destroy(headPhO);
    }

    void BuildModel()
    {
        body = new GameObject("Body"); body.transform.SetParent(transform);
        body.transform.localPosition = Vector3.zero;
        body.transform.localScale = Vector3.one * bodyScale;

        P(body,"Torso",PrimitiveType.Cube,V(0,1.05f,0),V(0.34f,0.44f,0.18f),shirtColor);
        P(body,"Collar",PrimitiveType.Cube,V(0,1.28f,0.04f),V(0.16f,0.04f,0.06f),shirtColor*0.9f);
        P(body,"Head",PrimitiveType.Sphere,V(0,1.50f,0),V(0.22f,0.24f,0.22f),skinColor);
        P(body,"Hair",PrimitiveType.Sphere,V(0,1.56f,-0.02f),V(0.23f,0.16f,0.23f),hairColor);
        P(body,"HairF",PrimitiveType.Cube,V(0,1.58f,0.08f),V(0.18f,0.04f,0.04f),hairColor);
        P(body,"Neck",PrimitiveType.Cube,V(0,1.34f,0),V(0.08f,0.08f,0.08f),skinColor);
        P(body,"EyeL",PrimitiveType.Sphere,V(-0.04f,1.52f,0.10f),V(0.03f,0.03f,0.02f),C(0.15f,0.12f,0.10f));
        P(body,"EyeR",PrimitiveType.Sphere,V(0.04f,1.52f,0.10f),V(0.03f,0.03f,0.02f),C(0.15f,0.12f,0.10f));
        P(body,"Nose",PrimitiveType.Cube,V(0,1.48f,0.11f),V(0.02f,0.03f,0.02f),skinColor*0.95f);
        P(body,"EarL",PrimitiveType.Cube,V(-0.11f,1.50f,0),V(0.02f,0.04f,0.03f),skinColor*0.95f);
        P(body,"EarR",PrimitiveType.Cube,V(0.11f,1.50f,0),V(0.02f,0.04f,0.03f),skinColor*0.95f);
        if(hasGlasses){
            P(body,"GlL",PrimitiveType.Cube,V(-0.04f,1.52f,0.115f),V(0.035f,0.025f,0.005f),C(0.18f,0.18f,0.20f));
            P(body,"GlR",PrimitiveType.Cube,V(0.04f,1.52f,0.115f),V(0.035f,0.025f,0.005f),C(0.18f,0.18f,0.20f));
            P(body,"GlBr",PrimitiveType.Cube,V(0,1.52f,0.115f),V(0.03f,0.008f,0.005f),C(0.18f,0.18f,0.20f));
        }
        P(body,"ArmL",PrimitiveType.Cube,V(-0.22f,1.02f,0),V(0.10f,0.40f,0.10f),shirtColor);
        P(body,"HandL",PrimitiveType.Cube,V(-0.22f,0.78f,0),V(0.07f,0.08f,0.06f),skinColor);
        P(body,"ArmR",PrimitiveType.Cube,V(0.22f,1.02f,0),V(0.10f,0.40f,0.10f),shirtColor);
        P(body,"HandR",PrimitiveType.Cube,V(0.22f,0.78f,0),V(0.07f,0.08f,0.06f),skinColor);
        P(body,"Watch",PrimitiveType.Cube,V(-0.22f,0.82f,0.04f),V(0.04f,0.02f,0.05f),C(0.20f,0.20f,0.22f));

        var ll=new GameObject("HipL");ll.transform.SetParent(body.transform);ll.transform.localPosition=V(-0.08f,0.82f,0);
        P(ll,"Thigh",PrimitiveType.Cube,V(0,-0.12f,0),V(0.13f,0.24f,0.13f),pantsColor);
        var knL=new GameObject("KneeL");knL.transform.SetParent(ll.transform);knL.transform.localPosition=V(0,-0.24f,0);
        P(knL,"Shin",PrimitiveType.Cube,V(0,-0.10f,0),V(0.11f,0.20f,0.11f),pantsColor);
        P(knL,"Shoe",PrimitiveType.Cube,V(0,-0.22f,0.02f),V(0.10f,0.06f,0.15f),shoeColor);
        lL=ll.transform; kL=knL.transform;

        var rr=new GameObject("HipR");rr.transform.SetParent(body.transform);rr.transform.localPosition=V(0.08f,0.82f,0);
        P(rr,"Thigh",PrimitiveType.Cube,V(0,-0.12f,0),V(0.13f,0.24f,0.13f),pantsColor);
        var knR=new GameObject("KneeR");knR.transform.SetParent(rr.transform);knR.transform.localPosition=V(0,-0.24f,0);
        P(knR,"Shin",PrimitiveType.Cube,V(0,-0.10f,0),V(0.11f,0.20f,0.11f),pantsColor);
        P(knR,"Shoe",PrimitiveType.Cube,V(0,-0.22f,0.02f),V(0.10f,0.06f,0.15f),shoeColor);
        lR=rr.transform; kR=knR.transform;

        P(body,"Belt",PrimitiveType.Cube,V(0,0.83f,0),V(0.35f,0.04f,0.19f),C(0.22f,0.18f,0.12f));
        P(body,"Buckle",PrimitiveType.Cube,V(0,0.83f,0.10f),V(0.04f,0.03f,0.01f),C(0.65f,0.60f,0.40f));

        bagO=new GameObject("Bag");bagO.transform.SetParent(body.transform);bagO.transform.localPosition=V(0,0.95f,-0.18f);
        P(bagO,"Bd",PrimitiveType.Cube,Vector3.zero,V(0.28f,0.35f,0.14f),bagColor);
        P(bagO,"Fl",PrimitiveType.Cube,V(0,0.13f,0.05f),V(0.26f,0.10f,0.04f),bagColor*0.9f);
        P(bagO,"Zp",PrimitiveType.Cube,V(0,0.02f,0.075f),V(0.18f,0.008f,0.005f),C(0.65f,0.60f,0.40f));
        P(bagO,"SL",PrimitiveType.Cube,V(-0.10f,0.08f,0.06f),V(0.025f,0.30f,0.02f),bagColor*0.85f);
        P(bagO,"SR",PrimitiveType.Cube,V(0.10f,0.08f,0.06f),V(0.025f,0.30f,0.02f),bagColor*0.85f);

        lapO=new GameObject("Lap");lapO.transform.SetParent(body.transform);lapO.transform.localPosition=V(0,0.95f,-0.22f);
        P(lapO,"Bs",PrimitiveType.Cube,Vector3.zero,V(0.30f,0.015f,0.20f),C(0.55f,0.55f,0.58f));
        P(lapO,"KB",PrimitiveType.Cube,V(0,0.01f,-0.02f),V(0.24f,0.005f,0.12f),C(0.20f,0.20f,0.22f));
        var sc=P(lapO,"Sc",PrimitiveType.Cube,V(0,0.10f,-0.095f),V(0.30f,0.19f,0.01f),C(0.55f,0.55f,0.58f));
        sc.transform.localRotation=Quaternion.Euler(-15,0,0);
        P(sc,"Dp",PrimitiveType.Cube,V(0,0.005f,-0.006f),V(0.26f,0.15f,0.003f),C(0.18f,0.30f,0.50f));

        bookO=new GameObject("Bks");bookO.transform.SetParent(body.transform);bookO.transform.localPosition=V(0.25f,0.90f,0.08f);
        Color[]bc={C(0.55f,0.18f,0.15f),C(0.15f,0.28f,0.48f),C(0.18f,0.42f,0.22f)};
        for(int i=0;i<3;i++) P(bookO,$"B{i}",PrimitiveType.Cube,V(0,i*0.028f,0),V(0.16f,0.025f,0.22f),bc[i]);
        P(bookO,"Nb",PrimitiveType.Cube,V(0.01f,0.09f,0),V(0.14f,0.01f,0.20f),C(0.85f,0.82f,0.35f));

        // Coffee cup - optional prop (40% chance)
        hasCoffee = Random.value < 0.4f;
        if (hasCoffee)
        {
            cupO = new GameObject("Cup"); cupO.transform.SetParent(body.transform);
            cupO.transform.localPosition = V(0.35f, 0.88f, 0.05f);
            P(cupO, "Cm", PrimitiveType.Cylinder, V(0, 0, 0), V(0.025f, 0.04f, 0.025f), C(0.95f, 0.95f, 0.95f));
            P(cupO, "Li", PrimitiveType.Cylinder, V(0, 0.045f, 0), V(0.02f, 0.005f, 0.02f), C(0.2f, 0.15f, 0.10f));
        }

        // Headphones - optional prop (30% chance)
        hasHeadphones = Random.value < 0.3f;
        if (hasHeadphones)
        {
            headPhO = new GameObject("HP"); headPhO.transform.SetParent(body.transform);
            headPhO.transform.localPosition = V(0, 1.55f, 0);
            P(headPhO, "Bn", PrimitiveType.Cube, V(0, 0, 0), V(0.32f, 0.02f, 0.04f), C(0.15f, 0.15f, 0.18f));
            P(headPhO, "EaL", PrimitiveType.Cylinder, V(-0.16f, -0.04f, 0), V(0.03f, 0.02f, 0.03f), C(0.20f, 0.20f, 0.22f));
            P(headPhO, "EaR", PrimitiveType.Cylinder, V(0.16f, -0.04f, 0), V(0.03f, 0.02f, 0.03f), C(0.20f, 0.20f, 0.22f));
        }
    }

    Vector3 V(float x,float y,float z)=>new Vector3(x,y,z);
    Color C(float r,float g,float b)=>new Color(r,g,b);
    GameObject P(GameObject p,string n,PrimitiveType t,Vector3 pos,Vector3 s,Color c){
        var o=GameObject.CreatePrimitive(t);o.name=n;o.transform.SetParent(p.transform);
        o.transform.localPosition=pos;o.transform.localScale=s;
        var rn=o.GetComponent<Renderer>();var m=new Material(rn.sharedMaterial);m.color=c;rn.sharedMaterial=m;
        DestroyImmediate(o.GetComponent<Collider>());return o;
    }

    /// <summary>
    /// Info about a ghost object (bag/laptop/book) placed at a seat.
    /// Used by YoloCapture for training data and ghost detection.
    /// </summary>
    [System.Serializable]
    public struct GhostObjectInfo
    {
        public string objName;      // "bag", "laptop", "book"
        public Vector3 worldPos;     // World position
        public float widthM;        // Physical width in meters
        public float heightM;       // Physical height in meters
        public string seatId;       // Which seat this belongs to

        public GhostObjectInfo(string name, Vector3 pos, float w, float h, string sid)
        {
            objName = name;
            worldPos = pos;
            widthM = w;
            heightM = h;
            seatId = sid;
        }
    }

    /// <summary>
    /// Returns list of ghost objects (bag/laptop/book) that are placed at this seat.
    /// Only returns objects that are NOT being carried (i.e., placed at desk/chair).
    /// Used for YOLO training data generation and ghost detection.
    /// </summary>
    public List<GhostObjectInfo> GetGhostObjects()
    {
        var list = new List<GhostObjectInfo>();

        // Bag - when placed (not parented to body), it's on the chair
        // Physical size: ~0.28m wide x 0.35m tall
        if (bagO != null && bagO.transform.parent != body.transform)
        {
            list.Add(new GhostObjectInfo("bag", bagO.transform.position, 0.28f, 0.35f, assignedSeatId));
        }

        // Laptop - when placed, it's on the desk
        // Physical size: ~0.30m wide x 0.20m tall (screen)
        if (lapO != null && lapO.transform.parent != body.transform)
        {
            list.Add(new GhostObjectInfo("laptop", lapO.transform.position, 0.30f, 0.20f, assignedSeatId));
        }

        // Books - when placed, they're on the desk
        // Physical size: ~0.16m wide x 0.08m tall (stack of 3)
        if (bookO != null && bookO.transform.parent != body.transform)
        {
            list.Add(new GhostObjectInfo("book", bookO.transform.position, 0.16f, 0.08f, assignedSeatId));
        }

        // Coffee cup - when placed, on desk
        // Physical size: ~0.05m wide x 0.08m tall
        if (cupO != null && cupO.transform.parent != body.transform)
        {
            list.Add(new GhostObjectInfo("cup", cupO.transform.position, 0.05f, 0.08f, assignedSeatId));
        }

        // Headphones - when placed (on desk), on desk or nearby
        if (headPhO != null && headPhO.transform.parent != body.transform)
        {
            list.Add(new GhostObjectInfo("headphones", headPhO.transform.position, 0.20f, 0.10f, assignedSeatId));
        }

        return list;
    }
}
