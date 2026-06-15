package pl.pwr.rl.wavearena;

import org.bukkit.command.Command;
import org.bukkit.command.CommandExecutor;
import org.bukkit.command.CommandSender;
import org.bukkit.entity.Player;

public class WaveArenaCommand implements CommandExecutor {

    private final WaveArenaPlugin plugin;

    public WaveArenaCommand(WaveArenaPlugin plugin) {
        this.plugin = plugin;
    }

    @Override
    public boolean onCommand(CommandSender sender, Command command, String label, String[] args) {
        if (args.length == 0) {
            sender.sendMessage("Usage: /wavearena <reset|next|status|bridge|reload|demo preset|demo random>");
            return true;
        }

        WaveManager wm = plugin.getWaveManager();
        String sub = args[0].toLowerCase();

        if (sub.equals("demo")) {
            if (args.length >= 2 && args[1].equalsIgnoreCase("stop")) {
                DemoRunner.forceReset(sender);
                return true;
            }
            if (args.length < 2) {
                sender.sendMessage("Usage: /wavearena demo <preset|random|stop>");
                sender.sendMessage("  preset — stala kolejnosc fal (demo_wave_sequence.yaml)");
                sender.sendMessage("  random — losowy typ moba na kazdej fali");
                sender.sendMessage("  stop   — reset gdy demo sie zawiesilo");
                return true;
            }
            String mode = args[1].toLowerCase();
            if (!mode.equals("preset") && !mode.equals("random")) {
                sender.sendMessage("Tryb: preset lub random");
                return true;
            }
            if (wm.getAgent() == null) {
                sender.sendMessage("Agent '" + plugin.getArenaConfig().agentUsername
                        + "' musi byc online na serwerze.");
                return true;
            }
            DemoRunner.launch(plugin, sender, mode);
            return true;
        }

        switch (sub) {
            case "reset" -> {
                wm.resetEpisode();
                sender.sendMessage("Episode reset. Wave=" + wm.currentWave
                        + " | alive=" + wm.countAliveMobs());
                if (wm.getAgent() == null) {
                    sender.sendMessage("UWAGA: Gracz '" + plugin.getArenaConfig().agentUsername
                            + "' nie jest online — dołącz tym nickiem lub zmień agent-username w config.yml");
                }
            }
            case "next" -> {
                wm.clearArenaMobs();
                wm.startNextWave();
                sender.sendMessage("Spawned wave " + wm.currentWave);
            }
            case "status" -> {
                sender.sendMessage(String.format(
                        "Wave %d | alive %d | max_wave %d | step %d | done %s | failed %s",
                        wm.currentWave, wm.countAliveMobs(), wm.maxWaveReached,
                        wm.episodeStep, wm.episodeDone, wm.waveFailed));
                Player agent = wm.getAgent();
                if (agent != null) {
                    sender.sendMessage("Agent HP: " + agent.getHealth());
                } else {
                    sender.sendMessage("Agent offline: " + plugin.getArenaConfig().agentUsername);
                }
            }
            case "bridge" -> sender.sendMessage("Bridge port: " + plugin.getArenaConfig().bridgePort);
            case "reload" -> {
                plugin.getArenaConfig().reload();
                sender.sendMessage("WaveArena config przeładowany. Mob-types: "
                        + plugin.getArenaConfig().mobTypes);
                wm.clearArenaMobs();
                sender.sendMessage("Usunięto moby areny. Użyj /wavearena reset lub poczekaj na reset z treningu.");
            }
            default -> sender.sendMessage("Unknown subcommand.");
        }
        return true;
    }
}
