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

    public String worldName;
    public double centerX, centerY, centerZ;
    public double radius;

    public List<Integer> mobCounts = new ArrayList<>();
    public List<EntityType> mobTypes = new ArrayList<>();
    public List<Location> spawnSlots = new ArrayList<>();

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
}
