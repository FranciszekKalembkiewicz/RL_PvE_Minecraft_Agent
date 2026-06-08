package pl.pwr.rl.wavearena;

import org.bukkit.GameMode;
import org.bukkit.Location;
import org.bukkit.Material;
import org.bukkit.World;
import org.bukkit.inventory.ItemStack;
import org.bukkit.potion.PotionEffect;
import org.bukkit.potion.PotionEffectType;
import org.bukkit.attribute.Attribute;
import org.bukkit.entity.Entity;
import org.bukkit.entity.LivingEntity;
import org.bukkit.entity.Mob;
import org.bukkit.entity.Player;
import org.bukkit.util.Vector;
import org.bukkit.entity.EntityType;
import org.bukkit.event.player.PlayerRespawnEvent;
import org.bukkit.scheduler.BukkitTask;

import java.util.ArrayList;
import java.util.List;

public class WaveManager {

    private final WaveArenaPlugin plugin;
    private final ArenaConfig config;

    public int currentWave = 0;
    public int maxWaveReached = 0;
    public int episodeStep = 0;
    public boolean episodeActive = false;
    public boolean episodeDone = false;
    public boolean waveClearedThisStep = false;
    public boolean waveFailed = false;
    public int killsThisStep = 0;
    public float damageDealtThisStep = 0f;

    private EntityType currentWaveMobType;
    private long waveStartMs = 0;
    private int pauseTicksRemaining = 0;
    private BukkitTask nextWaveTask = null;
    private int lastAttackStep = -10_000;
    private int lastTurnStep = -10_000;

    public WaveManager(WaveArenaPlugin plugin, ArenaConfig config) {
        this.plugin = plugin;
        this.config = config;
    }

    public Player getAgent() {
        return plugin.getServer().getPlayerExact(config.agentUsername);
    }

    public World getArenaWorld() {
        World w = plugin.getServer().getWorld(config.worldName);
        if (w == null && !plugin.getServer().getWorlds().isEmpty()) {
            w = plugin.getServer().getWorlds().get(0);
        }
        return w;
    }

    public synchronized void onAgentDeath() {
        failEpisode();
    }

    public synchronized void onAgentRespawn(PlayerRespawnEvent event) {
        World world = getArenaWorld();
        if (world == null) return;
        event.setRespawnLocation(config.centerLocation(world));
    }

    /** Koniec epizodu po śmierci — usuwa moby, blokuje kolejne fale. */
    public synchronized void failEpisode() {
        cancelNextWaveTask();
        clearArenaMobs();
        pauseTicksRemaining = 0;
        episodeDone = true;
        episodeActive = false;
        waveFailed = true;
    }

    private void cancelNextWaveTask() {
        if (nextWaveTask != null) {
            nextWaveTask.cancel();
            nextWaveTask = null;
        }
    }

    public synchronized void resetEpisode() {
        cancelNextWaveTask();
        clearArenaMobs();
        currentWave = 0;
        maxWaveReached = 0;
        episodeStep = 0;
        episodeActive = true;
        episodeDone = false;
        waveClearedThisStep = false;
        waveFailed = false;
        pauseTicksRemaining = 0;
        lastAttackStep = -10_000;
        lastTurnStep = -10_000;

        World world = getArenaWorld();
        if (world == null) {
            episodeActive = false;
            episodeDone = true;
            return;
        }

        Player agent = getAgent();
        if (agent != null) {
            reviveAndEquipAgent(agent, world);
        }

        startNextWave();
    }

    private void reviveAndEquipAgent(Player agent, World world) {
        Location center = config.centerLocation(world);
        if (agent.isDead()) {
            agent.spigot().respawn();
        }
        agent.teleport(center);
        agent.setHealth(config.agentMaxHp);
        agent.setFoodLevel(20);
        agent.setSaturation(20f);
        agent.setGameMode(GameMode.SURVIVAL);
        agent.setFireTicks(0);
        equipAgentKit(agent);
    }

    public synchronized void startNextWave() {
        if (episodeDone || !episodeActive) return;

        if (currentWave >= config.maxWaves) {
            episodeDone = true;
            episodeActive = false;
            return;
        }

        clearArenaMobs();

        currentWave++;
        currentWaveMobType = config.randomMobType();
        waveStartMs = System.currentTimeMillis();
        waveClearedThisStep = false;
        waveFailed = false;

        teleportAgentToCenter();
        spawnWaveMobs();
        refreshMobTargets();
    }

    private void teleportAgentToCenter() {
        Player agent = getAgent();
        World world = getArenaWorld();
        if (agent != null && world != null && !agent.isDead()) {
            agent.teleport(config.centerLocation(world));
        }
    }

    private void refreshMobTargets() {
        Player agent = getAgent();
        if (agent == null) return;
        for (LivingEntity mob : aliveMobs()) {
            if (mob instanceof Mob m) {
                m.setTarget(agent);
            }
        }
    }

    private void spawnWaveMobs() {
        World world = getArenaWorld();
        if (world == null) return;

        int count = config.mobCountForWave(currentWave);
        for (int i = 0; i < count; i++) {
            if (i >= config.spawnSlots.size()) break;
            Location loc = config.spawnSlots.get(i).clone();
            loc.setWorld(world);

            LivingEntity mob = (LivingEntity) world.spawnEntity(loc, currentWaveMobType);
            mob.addScoreboardTag(ArenaConfig.MOB_TAG);
            mob.setRemoveWhenFarAway(false);
            mob.setPersistent(true);
            if (mob instanceof Mob m) {
                m.setTarget(getAgent());
            }
            if (mob.getAttribute(Attribute.GENERIC_MAX_HEALTH) != null) {
                mob.getAttribute(Attribute.GENERIC_MAX_HEALTH).setBaseValue(config.agentMaxHp);
                mob.setHealth(config.agentMaxHp);
            }
            mob.addPotionEffect(new PotionEffect(
                    PotionEffectType.FIRE_RESISTANCE,
                    20 * 60 * 20,
                    0,
                    false,
                    false
            ));
        }
    }

    private void equipAgentKit(Player agent) {
        agent.getInventory().clear();
        agent.getInventory().setItemInMainHand(new ItemStack(Material.IRON_SWORD));
        agent.getInventory().setChestplate(new ItemStack(Material.LEATHER_CHESTPLATE));
        agent.getInventory().setLeggings(new ItemStack(Material.LEATHER_LEGGINGS));
    }

    public void clearArenaMobs() {
        World world = getArenaWorld();
        if (world == null) return;
        for (Entity e : world.getEntities()) {
            if (e.getScoreboardTags().contains(ArenaConfig.MOB_TAG)) {
                e.remove();
            }
        }
    }

    public int countAliveMobs() {
        int n = 0;
        World world = getArenaWorld();
        if (world == null) return 0;
        for (Entity e : world.getEntities()) {
            if (e.getScoreboardTags().contains(ArenaConfig.MOB_TAG) && e instanceof LivingEntity le && !le.isDead()) {
                n++;
            }
        }
        return n;
    }

    public List<LivingEntity> aliveMobs() {
        List<LivingEntity> list = new ArrayList<>();
        World world = getArenaWorld();
        if (world == null) return list;
        for (Entity e : world.getEntities()) {
            if (e.getScoreboardTags().contains(ArenaConfig.MOB_TAG) && e instanceof LivingEntity le && !le.isDead()) {
                list.add(le);
            }
        }
        return list;
    }

    public synchronized StepResult executeStep(int action) {
        killsThisStep = 0;
        damageDealtThisStep = 0f;
        waveClearedThisStep = false;
        waveFailed = false;

        if (!episodeActive || episodeDone) {
            return StepResult.ok();
        }

        Player agent = getAgent();
        if (agent == null) {
            failEpisode();
            return StepResult.error("agent_offline");
        }

        if (agent.isDead() || agent.getHealth() <= 0) {
            failEpisode();
            return StepResult.ok();
        }

        if (pauseTicksRemaining > 0) {
            pauseTicksRemaining -= config.stepTicks;
            if (pauseTicksRemaining < 0) pauseTicksRemaining = 0;
        } else {
            applyAction(agent, action);
            tickWaveLogic(agent);
        }

        episodeStep++;

        if (agent.getHealth() <= 0 || agent.isDead()) {
            failEpisode();
        }

        long elapsed = System.currentTimeMillis() - waveStartMs;
        if (!episodeDone && pauseTicksRemaining <= 0 && countAliveMobs() > 0
                && elapsed > config.waveTimeoutSec * 1000L) {
            failEpisode();
        }

        return StepResult.ok();
    }

    private void applyAction(Player agent, int action) {
        float yawRad = (float) Math.toRadians(agent.getLocation().getYaw());
        Vector forward = new Vector(-Math.sin(yawRad), 0, Math.cos(yawRad));
        Vector right = new Vector(Math.cos(yawRad), 0, Math.sin(yawRad));
        Vector vel = agent.getVelocity().clone();
        double s = config.moveSpeed;

        switch (action) {
            case 0 -> vel.add(forward.multiply(s));
            case 1 -> vel.add(forward.multiply(-s));
            case 2 -> vel.add(right.multiply(-s));
            case 3 -> vel.add(right.multiply(s));
            case 4 -> {
                if (canAttackNow()) {
                    performAttack(agent);
                    lastAttackStep = episodeStep;
                }
            }
            case 5 -> { /* noop */ }
            case 6 -> {
                if (agent.isOnGround()) vel.setY(0.42);
            }
            case 7 -> {
                if (canTurnNow()) {
                    Location loc = agent.getLocation();
                    loc.setYaw(loc.getYaw() + 45f);
                    agent.teleport(loc);
                    lastTurnStep = episodeStep;
                }
            }
            default -> { }
        }

        if (action != 4 && action != 7) {
            vel.setX(Math.max(-0.8, Math.min(0.8, vel.getX())));
            vel.setZ(Math.max(-0.8, Math.min(0.8, vel.getZ())));
            agent.setVelocity(vel);
        }
    }

    private void performAttack(Player agent) {
        LivingEntity best = null;
        double bestDist = config.attackRange;
        for (LivingEntity mob : aliveMobs()) {
            double d = mob.getLocation().distance(agent.getLocation());
            if (d <= bestDist) {
                bestDist = d;
                best = mob;
            }
        }
        if (best != null) {
            float hpBefore = (float) best.getHealth();
            best.damage(config.attackDamage, agent);
            float dealt = Math.max(0, hpBefore - (float) best.getHealth());
            damageDealtThisStep += dealt;
            if (best.isDead() || best.getHealth() <= 0) {
                killsThisStep++;
            }
            agent.swingMainHand();
        }
    }

    private boolean canAttackNow() {
        if (!config.realFightEnabled) return true;
        int cdSteps = cooldownToSteps(config.attackCooldownTicks);
        return episodeStep - lastAttackStep >= cdSteps;
    }

    private boolean canTurnNow() {
        if (!config.realFightEnabled) return true;
        int cdSteps = cooldownToSteps(config.turnCooldownTicks);
        return episodeStep - lastTurnStep >= cdSteps;
    }

    private int cooldownToSteps(int cooldownTicks) {
        int stepTicks = Math.max(1, config.stepTicks);
        int cdTicks = Math.max(0, cooldownTicks);
        return Math.max(1, (int) Math.ceil(cdTicks / (double) stepTicks));
    }

    public synchronized void onArenaMobDeath() {
        if (!episodeActive || episodeDone || pauseTicksRemaining > 0) {
            return;
        }
        if (currentWave > 0 && countAliveMobs() == 0) {
            Player agent = getAgent();
            if (agent != null && !agent.isDead()) {
                handleWaveCleared(agent);
            }
        }
    }

    private void tickWaveLogic(Player agent) {
        if (pauseTicksRemaining > 0) return;

        if (currentWave > 0 && countAliveMobs() == 0) {
            handleWaveCleared(agent);
        }
    }

    private void handleWaveCleared(Player agent) {
        if (pauseTicksRemaining > 0 || nextWaveTask != null) {
            return;
        }
        waveClearedThisStep = true;
        maxWaveReached = Math.max(maxWaveReached, currentWave);

        if (agent != null && !agent.isDead()) {
            World world = getArenaWorld();
            if (world != null) {
                agent.teleport(config.centerLocation(world));
            }
            if (config.healBetweenWaves) {
                agent.setHealth(config.agentMaxHp);
            }
        }

        if (currentWave >= config.maxWaves) {
            episodeDone = true;
            episodeActive = false;
            return;
        }

        pauseTicksRemaining = config.interWavePauseTicks;
        cancelNextWaveTask();
        nextWaveTask = plugin.getServer().getScheduler().runTaskLater(plugin, () -> {
            synchronized (WaveManager.this) {
                nextWaveTask = null;
                if (episodeActive && !episodeDone) {
                    startNextWave();
                }
            }
        }, config.interWavePauseTicks);
    }

    public static class StepResult {
        public final boolean success;
        public final String error;

        private StepResult(boolean success, String error) {
            this.success = success;
            this.error = error;
        }

        public static StepResult ok() {
            return new StepResult(true, null);
        }

        public static StepResult error(String msg) {
            return new StepResult(false, msg);
        }
    }
}
