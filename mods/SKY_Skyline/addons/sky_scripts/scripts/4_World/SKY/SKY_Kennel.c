/*
	Guard kennel (D62, ROADMAP ideas 5 and 9). DayZ creatures need a rig and an AI graph that the
	procedural pipeline cannot make, so the dog is part of the kennel model and its job is done by the
	server (DECISIONS D62):
	- placing the kennel binds it to the placer (OnPlacementComplete, itembase.c:3959);
	- while the owner is offline (up to KENNEL_GUARD_S after they were last seen) the kennel guards:
	  nothing can be taken out or put in, the kennel cannot be picked up, and its cargo is not shown;
	- a stranger within KENNEL_BARK_RADIUS makes the dog bark (sound for nearby players + an AI noise
	  target, so infected come to look), at most every KENNEL_BARK_MS;
	- a guard dog within DOG_REPEL_* keeps rats off players and bases (SKY_CreatureLife).
	Base: vanilla DeployableContainer_Base (container_base.c:32; placement actions as SeaChest,
	camping.c:5). Guard checks use only server state; the client gets one synced bool for its UI.
	Persistence: owner id + last-seen UTC time, versioned (KENNEL_STORE_VERSION).
	Security review D62: no damage while guarding (H1); stack split / combine out of a guarded kennel is
	refused in modded ItemBase below (H2, playerbase.c:6309-6370 never asks the container); only an empty
	kennel can be picked up (M2); a bad save block keeps the kennel (M3). The synced guard bool shows
	whether the owner is away - by design, the dog visibly guards (L1).
*/
class SKY_Kennel extends DeployableContainer_Base
{
	protected string m_SkyOwner;		//!< server: owner PlayerIdentity.GetId() (persisted)
	protected int m_SkyLastSeen;		//!< server: SKY_Time.NowUtc() when the owner was last online (persisted)
	protected int m_SkyNextBark;		//!< server: earliest next bark (ms)
	protected bool m_SkyGuarding;		//!< synced
	static int s_SkyGuardCount;			//!< guarding kennels in this process: ItemBase checks skip when 0 (D94 perf
	protected bool m_SkyCounted;		//!< audit M: the CE always seeds kennels, so counting all of them never gated)

	void SKY_Kennel()
	{
		m_HalfExtents = Vector(0.55, 0.5, 0.95);
		RegisterNetSyncVariableBool("m_SkyGuarding");
		if (g_Game.IsServer())
			SKY_CreatureLife.RegisterKennel(this);
	}

	void ~SKY_Kennel()
	{
		if (m_SkyCounted)
			s_SkyGuardCount--;
		SKY_CreatureLife.UnregisterKennel(this);
	}

	//! Keeps s_SkyGuardCount in step with m_SkyGuarding (server: SkySetGuarding; client: the synced bool).
	protected void SkyRecount()
	{
		if (m_SkyGuarding == m_SkyCounted)
			return;
		m_SkyCounted = m_SkyGuarding;
		if (m_SkyCounted)
			s_SkyGuardCount++;
		else
			s_SkyGuardCount--;
	}

	override void OnVariablesSynchronized()
	{
		super.OnVariablesSynchronized();
		SkyRecount();
	}

	override void OnPlacementComplete(Man player, vector position = "0 0 0", vector orientation = "0 0 0")
	{
		super.OnPlacementComplete(player, position, orientation);
		if (!g_Game.IsServer() || !player || !player.GetIdentity())
			return;
		m_SkyOwner = player.GetIdentity().GetId();
		m_SkyLastSeen = SKY_Time.NowUtc();
		SkySetGuarding(false);
	}

	//! Security review (full audit M2): a guarded kennel cannot be damaged or moved, so it must not seal a door.
	//! Checked on the server too (actiondeployobject.c:67 re-runs CanBePlaced with the server hologram).
	override bool CanBePlaced(Man player, vector position)
	{
		if (!super.CanBePlaced(player, position))
			return false;
		return !SkyNearDoor(position);
	}

	override string CanBePlacedFailMessage(Man player, vector position)
	{
		if (SkyNearDoor(position))
			return "Kennels go outdoors, clear of doors and gates";
		return super.CanBePlacedFailMessage(player, position);
	}

	protected vector m_SkyDoorPos = "0 -10000 0";	//!< last door check (the hologram asks every frame)
	protected bool m_SkyDoorNear;
	protected int m_SkyDoorAt;						//!< g_Game.GetTime() of the last scan
	protected ref array<Object> m_SkyDoorObjs;

	//! Server: exact (cached only for the same spot). Client hologram (re-review perf M): at most one scan per
	//! 250 ms while the hologram moves less than 0.5 m - the hint may lag a frame, the server re-checks.
	protected bool SkyNearDoor(vector position)
	{
		float d2 = vector.DistanceSq(position, m_SkyDoorPos);
		int now = g_Game.GetTime();
		if (d2 < 0.01 || (!g_Game.IsServer() && d2 < 0.25 && now - m_SkyDoorAt < 250))
			return m_SkyDoorNear;
		m_SkyDoorPos = position;
		m_SkyDoorAt = now;
		m_SkyDoorNear = SkyScanDoors(position);
		return m_SkyDoorNear;
	}

	protected bool SkyScanDoors(vector position)
	{
		if (!m_SkyDoorObjs)
			m_SkyDoorObjs = new array<Object>();
		array<Object> objs = m_SkyDoorObjs;
		objs.Clear();
		g_Game.GetObjectsAtPosition(position, SKY_Beasts.KENNEL_DOOR_SCAN, objs, null);
		float r2 = SKY_Beasts.KENNEL_DOOR_CLEAR * SKY_Beasts.KENNEL_DOOR_CLEAR;
		float base2 = SKY_Beasts.KENNEL_BASE_CLEAR * SKY_Beasts.KENNEL_BASE_CLEAR;
		foreach (Object o : objs)
		{
			// re-review sec M: player-built walls / gates (Fence, watchtower: basebuildingbase.c:2) are not
			// Buildings - a guarded kennel must not seal someone's base gate either
			if (BaseBuildingBase.Cast(o) && vector.DistanceSq(o.GetPosition(), position) < base2)
				return true;
			Building b = Building.Cast(o);
			if (!b)
				continue;
			// D94 security audit M2: indoors (stair landings, corridors, elevator cabs - SKY elevator doors are
			// animations, not Doors) a guarded kennel would seal what lies beyond: kennels are outdoor only
			vector mm[2];
			if (b.GetCollisionBox(mm))							// model-space box (object.c:376)
			{
				vector lp = b.WorldToModel(position);
				if (lp[0] > mm[0][0] && lp[0] < mm[1][0] && lp[1] > mm[0][1] - 0.5 && lp[1] < mm[1][1] && lp[2] > mm[0][2] && lp[2] < mm[1][2])
					return true;
			}
			int n = b.GetDoorCount();
			for (int i = 0; i < n; i++)
			{
				if (vector.DistanceSq(b.GetDoorSoundPos(i), position) < r2)	// world space (building.c:79)
					return true;
			}
		}
		return false;
	}

	bool SkyIsGuarding()
	{
		return m_SkyGuarding;
	}

	string SkyOwner()
	{
		return m_SkyOwner;
	}

	//! Server, from SKY_CreatureLife every 30 s. ownerOnline = the owner's identity is connected.
	void SkyUpdateGuard(bool ownerOnline, int nowUtc)
	{
		if (m_SkyOwner == "" || GetHierarchyParent())
		{
			SkySetGuarding(false);
			return;
		}
		if (ownerOnline)
		{
			m_SkyLastSeen = nowUtc;
			SkySetGuarding(false);
			return;
		}
		SkySetGuarding(nowUtc - m_SkyLastSeen <= SKY_Beasts.KENNEL_GUARD_S);
	}

	protected void SkySetGuarding(bool guarding)
	{
		// security D62 H1: a ruined container spills its cargo (container_base.c:94-100); set only on change
		// (perf review: was every 30 s per kennel) - GetAllowDamage, object.c:1187
		if (g_Game.IsServer() && GetAllowDamage() == guarding)
			SetAllowDamage(!guarding);
		if (guarding == m_SkyGuarding)
			return;
		m_SkyGuarding = guarding;
		SkyRecount();
		SetSynchDirty();
	}

	//! Server: may the dog bark now? Records the bark.
	bool SkyTryBark(int nowMs)
	{
		if (!m_SkyGuarding || nowMs < m_SkyNextBark)
			return false;
		m_SkyNextBark = nowMs + SKY_Beasts.KENNEL_BARK_MS;
		return true;
	}

	vector SkyBarkPos()
	{
		if (MemoryPointExists("bark"))
			return ModelToWorld(GetMemoryPointPos("bark"));
		return GetPosition();
	}

	// ---- guard: server state decides, the synced bool keeps the client UI consistent
	override bool CanReleaseCargo(EntityAI cargo)
	{
		if (m_SkyGuarding)
			return false;
		return super.CanReleaseCargo(cargo);
	}

	override bool CanReceiveItemIntoCargo(EntityAI item)
	{
		if (m_SkyGuarding)
			return false;
		return super.CanReceiveItemIntoCargo(item);
	}

	override bool CanReleaseAttachment(EntityAI attachment)
	{
		if (m_SkyGuarding)
			return false;
		return super.CanReleaseAttachment(attachment);
	}

	//! Only an empty kennel can be picked up (security D62 M2: re-placing makes the carrier the owner).
	protected bool SkyIsEmpty()
	{
		return !GetInventory() || !GetInventory().GetCargo() || GetInventory().GetCargo().GetItemCount() == 0;
	}

	override bool CanPutIntoHands(EntityAI parent)
	{
		if (m_SkyGuarding || !SkyIsEmpty())
			return false;
		return super.CanPutIntoHands(parent);
	}

	override bool CanPutInCargo(EntityAI parent)
	{
		if (m_SkyGuarding || !SkyIsEmpty())
			return false;
		return super.CanPutInCargo(parent);
	}

	override bool CanSwapItemInCargo(EntityAI child_entity, EntityAI new_entity)
	{
		if (m_SkyGuarding)
			return false;
		return super.CanSwapItemInCargo(child_entity, new_entity);
	}

	override bool CanDisplayCargo()
	{
		if (m_SkyGuarding)
			return false;
		return super.CanDisplayCargo();
	}

	// ---- persistence
	override void OnStoreSave(ParamsWriteContext ctx)
	{
		super.OnStoreSave(ctx);
		ctx.Write(SKY_Beasts.KENNEL_STORE_VERSION);
		ctx.Write(m_SkyOwner);
		ctx.Write(m_SkyLastSeen);
	}

	//! A bad SKY block never deletes the kennel and its cargo (security D62 M3): the kennel just loses
	//! its owner and stops guarding until someone places it again.
	override bool OnStoreLoad(ParamsReadContext ctx, int version)
	{
		if (!super.OnStoreLoad(ctx, version))
			return false;
		int v;
		if (!ctx.Read(v) || v < 1 || v > SKY_Beasts.KENNEL_STORE_VERSION || !ctx.Read(m_SkyOwner) || !ctx.Read(m_SkyLastSeen))
		{
			m_SkyOwner = "";
			m_SkyLastSeen = 0;
			return true;
		}
		if (m_SkyOwner.Length() > 64)						// identity ids are short hashes
			m_SkyOwner = "";
		int now = SKY_Time.NowUtc();
		if (m_SkyLastSeen > now)							// clock jump / corrupt value
			m_SkyLastSeen = now;
		return true;
	}

	//! Guard straight away after a restart (the owner is offline when the server starts); the 30 s
	//! director check corrects it once players connect.
	override void AfterStoreLoad()
	{
		super.AfterStoreLoad();
		if (g_Game.IsServer())
		{
			bool guarding = SKY_CreatureLife.IsKennelRegistered(this) && !GetHierarchyParent() && m_SkyOwner != "";
			if (SKY_Time.NowUtc() - m_SkyLastSeen > SKY_Beasts.KENNEL_GUARD_S)
				guarding = false;
			SkySetGuarding(guarding);
		}
	}
}

//! Security D62 H2: the server's split / combine handler (PlayerBase.HandleRemoteItemManipulation,
//! playerbase.c:6309-6370) moves quantity without asking the container. Every split path checks
//! ShouldSplitQuantity (itembase.c:1613) and CombineItems checks CanBeCombined (itembase.c:2310).
modded class ItemBase
{
	bool SkyInGuardedKennel()
	{
		if (SKY_Kennel.s_SkyGuardCount <= 0 || !GetHierarchyParent())	// none guarding, or a loose item: one compare
			return false;
		SKY_Kennel k = SKY_Kennel.Cast(GetHierarchyRoot());
		return k && k != this && k.SkyIsGuarding();
	}

	override protected bool ShouldSplitQuantity(float quantity)
	{
		if (SkyInGuardedKennel())
			return false;
		return super.ShouldSplitQuantity(quantity);
	}

	//! Full audit M1: items nested in a guarded kennel (in a backpack, attachments of a stored gun) are locked
	//! too - the kennel's own overrides only see its direct cargo.
	override bool CanReleaseCargo(EntityAI cargo)
	{
		if (SkyInGuardedKennel())
			return false;
		return super.CanReleaseCargo(cargo);
	}

	override bool CanReleaseAttachment(EntityAI attachment)
	{
		if (SkyInGuardedKennel())
			return false;
		return super.CanReleaseAttachment(attachment);
	}

	override bool CanReceiveItemIntoCargo(EntityAI item)
	{
		if (SkyInGuardedKennel())
			return false;
		return super.CanReceiveItemIntoCargo(item);
	}

	override bool CanReceiveAttachment(EntityAI attachment, int slotId)
	{
		if (SkyInGuardedKennel())
			return false;
		return super.CanReceiveAttachment(attachment, slotId);
	}

	override bool CanBeCombined(EntityAI other_item, bool reservation_check = true, bool stack_max_limit = false)
	{
		ItemBase other = ItemBase.Cast(other_item);
		if (SkyInGuardedKennel() || (other && other.SkyInGuardedKennel()))
			return false;
		return super.CanBeCombined(other_item, reservation_check, stack_max_limit);
	}
}
//! D94 security audit M1: vanilla actions that target an item (load a magazine from an ammo pile, craft, drain a
//! liquid) only refuse items in another player's hierarchy (actionbase.c:873-887), so a modified client could still
//! take things out of a guarded kennel by targeting them. Refuse any action whose target or held item sits inside a
//! guarding kennel; the kennel itself stays a valid target. Server and client run the same Can.
modded class ActionBase
{
	override bool Can(PlayerBase player, ActionTarget target, ItemBase item, int condition_mask)
	{
		if (SKY_Kennel.s_SkyGuardCount > 0)
		{
			if (item && item.SkyInGuardedKennel())
				return false;
			if (target)
			{
				ItemBase ti = ItemBase.Cast(target.GetObject());
				if (ti && ti.SkyInGuardedKennel())
					return false;
				ItemBase tp = ItemBase.Cast(target.GetParent());
				if (tp && tp.SkyInGuardedKennel())
					return false;
			}
		}
		return super.Can(player, target, item, condition_mask);
	}
}
