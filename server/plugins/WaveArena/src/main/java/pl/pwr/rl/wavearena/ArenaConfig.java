package pl.pwr.rl.wavearena;

import org.bukkit.Location;
import org.bukkit.World;
import org.bukkit.configuration.file.FileConfiguration;
import org.bukkit.entity.EntityType;

import java.util.ArrayList;
import java.util.List;
import java.util.Random;

public class ArenaConfig {

    public static final String MOB_TAG = "arena_mob";

    private final WaveArenaPlugin plugin;
    private final Random random = new Random();

    public int bridgePort;
    public int stepTicks;
    public int waveTimeoutSec;
    public int interWavePauseTicks;
    public boolean healBetweenWaves;
    public int maxWaves;
    public String agentUsername;
    public double agentMaxHp;
    public double attackRange;
    public double attackDamage;
    public double moveSpeed;
    public boolean realFightEnabled;
    public int attackCooldownTicks;
    public int turnCooldownTicks;
    public int jumpCooldownTicks;
    public float turnDegrees;
    public float turnDegreesPerTick;
    public float attackFaceDegrees;
    public float attackConeDegrees;
    public boolean faceTargetOnAttack;
    public boolean turnTowardTarget;
    public double skeletonSpawnFactor;
    public boolean skeletonFaceTarget;
    public float skeletonFaceSlewPerTick;
    public boolean skeletonInstantFace;
    public boolean skeletonFreeTurn;
    public boolean skeletonMoveTowardTarget;
    public float skeletonAttackFaceDegrees;

    public String worldName;
    public double centerX, centerY, centerZ;
    public double radius;

    public List<Integer> mobCounts = new ArrayList<>();
    public List<EntityType> mobTypes = new ArrayList<>();
    /** Jeśli niepusta — typ moba na falę 1..N (powtarza się przy dłuższym runie). */
    public List<EntityType> waveMobSequence = new ArrayList<>();
    public List<Location> spawnSlots = new ArrayList<>();
    /** Opcjonalna ścieżka do katalogu minecraft_rl_project (demo z /wavearena). */
    public String demoProjectRoot = "";

    public ArenaConfig(WaveArenaPlugin plugin) {
        this.plugin = plugin;
        reload();
    }

    public void reload() {
        plugin.saveDefaultConfig();
        plugin.reloadConfig();
        FileConfiguration c = plugin.getConfig();

        bridgePort = c.getInt("bridge-port", 5555);
        stepTicks = c.getInt("step-ticks", 2);
        waveTimeoutSec = c.getInt("wave-timeout-sec", 120);
        interWavePauseTicks = c.getInt("inter-wave-pause-ticks", 40);
        healBetweenWaves = c.getBoolean("heal-between-waves", true);
        maxWaves = c.getInt("max-waves", 10);
        agentUsername = c.getString("agent-username", "AgentBot");
        agentMaxHp = c.getDouble("agent-max-hp", 20.0);
        attackRange = c.getDouble("attack-range", 3.0);
        attackDamage = c.getDouble("attack-damage", 4.5);
        moveSpeed = c.getDouble("move-speed", 0.35);
        realFightEnabled = c.getBoolean("real-fight.enabled", false);
        attackCooldownTicks = c.getInt("real-fight.attack-cooldown-ticks", 20);
        turnCooldownTicks = c.getInt("real-fight.turn-cooldown-ticks", 20);
        jumpCooldownTicks = c.getInt("real-fight.jump-cooldown-ticks", 12);
        turnDegrees = (float) c.getDouble("real-fight.turn-degrees", 22.5);
        turnDegreesPerTick = (float) c.getDouble("real-fight.turn-degrees-per-tick", 2.5);
        attackFaceDegrees = (float) c.getDouble("real-fight.attack-face-degrees", 4.0);
        attackConeDegrees = (float) c.getDouble("real-fight.attack-cone-degrees", 70.0);
        faceTargetOnAttack = c.getBoolean("real-fight.face-target-on-attack", true);
        turnTowardTarget = c.getBoolean("real-fight.turn-toward-target", true);
        skeletonSpawnFactor = c.getDouble("skeleton-spawn-factor", 0.55);
        skeletonFaceTarget = c.getBoolean("skeleton-combat.face-target-each-step", true);
        skeletonFaceSlewPerTick = (float) c.getDouble("skeleton-combat.face-slew-degrees-per-tick", 3.0);
        skeletonInstantFace = c.getBoolean("skeleton-combat.instant-face", true);
        skeletonFreeTurn = c.getBoolean("skeleton-combat.free-turn", true);
        skeletonMoveTowardTarget = c.getBoolean("skeleton-combat.move-toward-target-on-forward", true);
        skeletonAttackFaceDegrees = (float) c.getDouble("skeleton-combat.attack-face-degrees", 12.0);
        demoProjectRoot = c.getString("demo.project-root", "");

        worldName = c.getString("arena.world", "world");
        centerX = c.getDouble("arena.center-x", 0.5);
        centerY = c.getDouble("arena.center-y", 64.0);
        centerZ = c.getDouble("arena.center-z", 0.5);
        radius = c.getDouble("arena.radius", 14.0);

        mobCounts.clear();
        for (int n : c.getIntegerList("mob-counts")) {
            mobCounts.add(n);
        }
        if (mobCounts.isEmpty()) {
            mobCounts.add(1);
            mobCounts.add(5);
        }

        mobTypes.clear();
        for (String s : c.getStringList("mob-types")) {
            try {
                mobTypes.add(EntityType.valueOf(s.toUpperCase()));
            } catch (IllegalArgumentException ignored) {
            }
        }
        if (mobTypes.isEmpty()) {
            mobTypes.add(EntityType.ZOMBIE);
        }

        waveMobSequence.clear();
        for (String s : c.getStringList("wave-mob-sequence")) {
            try {
                waveMobSequence.add(EntityType.valueOf(s.toUpperCase()));
            } catch (IllegalArgumentException ignored) {
            }
        }

        spawnSlots.clear();
        World world = plugin.getServer().getWorld(worldName);
        if (world == null && !plugin.getServer().getWorlds().isEmpty()) {
            world = plugin.getServer().getWorlds().get(0);
        }
        if (world != null) {
            for (Object entry : c.getMapList("spawn-slots")) {
                if (entry instanceof java.util.Map<?, ?> map) {
                    double x = toDouble(map.get("x"), centerX);
                    double y = toDouble(map.get("y"), centerY);
                    double z = toDouble(map.get("z"), centerZ);
                    spawnSlots.add(new Location(world, x, y, z));
                }
            }
        }
    }

    private static double toDouble(Object o, double def) {
        if (o instanceof Number n) return n.doubleValue();
        return def;
    }

    public Location centerLocation(World world) {
        return new Location(world, centerX, centerY, centerZ);
    }

    public int mobCountForWave(int wave) {
        int idx = wave - 1;
        if (idx < 0) idx = 0;
        if (idx >= mobCounts.size()) {
            return mobCounts.get(mobCounts.size() - 1);
        }
        return mobCounts.get(idx);
    }

    public EntityType randomMobType() {
        return mobTypes.get(random.nextInt(mobTypes.size()));
    }

    public EntityType mobTypeForWave(int wave) {
        if (!waveMobSequence.isEmpty()) {
            int idx = Math.max(0, wave - 1) % waveMobSequence.size();
            return waveMobSequence.get(idx);
        }
        return randomMobType();
    }
}
