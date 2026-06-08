package pl.pwr.rl.wavearena;

import org.bukkit.event.EventHandler;
import org.bukkit.event.EventPriority;
import org.bukkit.event.Listener;
import org.bukkit.event.entity.EntityDeathEvent;
import org.bukkit.event.entity.PlayerDeathEvent;
import org.bukkit.event.player.PlayerRespawnEvent;

public class ArenaListener implements Listener {

    private final WaveArenaPlugin plugin;

    public ArenaListener(WaveArenaPlugin plugin) {
        this.plugin = plugin;
    }

    @EventHandler(priority = EventPriority.MONITOR, ignoreCancelled = true)
    public void onAgentDeath(PlayerDeathEvent event) {
        if (!event.getEntity().getName().equalsIgnoreCase(plugin.getArenaConfig().agentUsername)) {
            return;
        }
        plugin.getWaveManager().onAgentDeath();
    }

    @EventHandler(priority = EventPriority.MONITOR, ignoreCancelled = true)
    public void onMobDeath(EntityDeathEvent event) {
        if (!event.getEntity().getScoreboardTags().contains(ArenaConfig.MOB_TAG)) {
            return;
        }
        plugin.getWaveManager().onArenaMobDeath();
    }

    @EventHandler(priority = EventPriority.MONITOR)
    public void onAgentRespawn(PlayerRespawnEvent event) {
        if (!event.getPlayer().getName().equalsIgnoreCase(plugin.getArenaConfig().agentUsername)) {
            return;
        }
        plugin.getWaveManager().onAgentRespawn(event);
    }
}
