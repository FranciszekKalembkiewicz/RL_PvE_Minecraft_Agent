package pl.pwr.rl.wavearena;

import org.bukkit.GameRule;
import org.bukkit.World;
import org.bukkit.plugin.java.JavaPlugin;

public class WaveArenaPlugin extends JavaPlugin {

    private ArenaConfig arenaConfig;
    private WaveManager waveManager;
    private BridgeServer bridgeServer;

    @Override
    public void onEnable() {
        arenaConfig = new ArenaConfig(this);
        waveManager = new WaveManager(this, arenaConfig);
        bridgeServer = new BridgeServer(this);
        bridgeServer.start();

        if (getCommand("wavearena") != null) {
            getCommand("wavearena").setExecutor(new WaveArenaCommand(this));
        }
        getServer().getPluginManager().registerEvents(new ArenaListener(this), this);

        World arenaWorld = waveManager.getArenaWorld();
        if (arenaWorld != null) {
            arenaWorld.setGameRule(GameRule.DO_DAYLIGHT_CYCLE, false);
            arenaWorld.setTime(13_000L);
            arenaWorld.setStorm(false);
        }

        getLogger().info("WaveArena enabled. Agent=" + arenaConfig.agentUsername
                + " bridge=" + arenaConfig.bridgePort);
    }

    @Override
    public void onDisable() {
        if (bridgeServer != null) {
            bridgeServer.stop();
        }
        if (waveManager != null) {
            waveManager.clearArenaMobs();
        }
    }

    public ArenaConfig getArenaConfig() {
        return arenaConfig;
    }

    public WaveManager getWaveManager() {
        return waveManager;
    }
}
