package pl.pwr.rl.wavearena;

import org.bukkit.command.CommandSender;
import org.bukkit.scheduler.BukkitRunnable;

import java.io.File;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.logging.Logger;

public final class DemoRunner {

    private static final AtomicBoolean RUNNING = new AtomicBoolean(false);

    private DemoRunner() {
    }

    public static boolean isRunning() {
        return RUNNING.get();
    }

    public static void forceReset(CommandSender sender) {
        RUNNING.set(false);
        sender.sendMessage("Flaga demo zresetowana — mozesz uruchomic ponownie.");
    }

    public static void launch(WaveArenaPlugin plugin, CommandSender sender, String mode) {
        if (RUNNING.get()) {
            sender.sendMessage("Demo juz dziala — poczekaj na koniec epizodu lub: /wavearena demo stop");
            return;
        }

        File projectRoot;
        File script;
        File logFile;
        try {
            projectRoot = resolveProjectRoot(plugin);
            script = new File(projectRoot, "scripts/run_demo.sh");
            logFile = new File(projectRoot, "logs/demo_last.log");
            if (!script.isFile()) {
                sender.sendMessage("Brak scripts/run_demo.sh w: " + projectRoot.getAbsolutePath());
                return;
            }
            File logsDir = logFile.getParentFile();
            if (logsDir != null && !logsDir.exists()) {
                //noinspection ResultOfMethodCallIgnored
                logsDir.mkdirs();
            }
        } catch (Exception e) {
            sender.sendMessage("Blad konfiguracji demo: " + e.getMessage());
            plugin.getLogger().warning("Demo config error: " + e.getMessage());
            return;
        }

        if (!RUNNING.compareAndSet(false, true)) {
            sender.sendMessage("Demo juz dziala — poczekaj na koniec epizodu.");
            return;
        }

        String label = "preset".equals(mode) ? "ustalone fale" : "losowe moby";
        sender.sendMessage("Uruchamiam demo dual (" + label + ")...");
        sender.sendMessage("Log: logs/demo_last.log");

        Logger log = plugin.getLogger();
        File finalLogFile = logFile;
        File finalProjectRoot = projectRoot;
        File finalScript = script;

        new BukkitRunnable() {
            @Override
            public void run() {
                int exit = -1;
                try {
                    ProcessBuilder pb = new ProcessBuilder(
                            "/bin/bash", finalScript.getAbsolutePath(), mode);
                    pb.directory(finalProjectRoot);
                    pb.redirectOutput(ProcessBuilder.Redirect.appendTo(finalLogFile));
                    pb.redirectError(ProcessBuilder.Redirect.appendTo(finalLogFile));
                    Process process = pb.start();
                    exit = process.waitFor();
                    log.info("Demo " + mode + " finished with exit " + exit);
                } catch (Exception e) {
                    log.warning("Demo failed: " + e.getMessage());
                } finally {
                    RUNNING.set(false);
                    int code = exit;
                    new BukkitRunnable() {
                        @Override
                        public void run() {
                            if (code == 0) {
                                sender.sendMessage("Demo zakonczone. Szczegoly: logs/demo_last.log");
                            } else {
                                sender.sendMessage("Demo zakonczone z bledem (exit " + code
                                        + "). Zobacz logs/demo_last.log");
                            }
                        }
                    }.runTask(plugin);
                }
            }
        }.runTaskAsynchronously(plugin);
    }

    private static File resolveProjectRoot(WaveArenaPlugin plugin) {
        String configured = plugin.getArenaConfig().demoProjectRoot;
        if (configured != null && !configured.isBlank()) {
            File fromConfig = new File(configured.trim());
            if (!fromConfig.isAbsolute()) {
                File serverDir = plugin.getServer().getWorldContainer();
                if (serverDir != null) {
                    fromConfig = new File(serverDir, configured.trim());
                }
            }
            if (fromConfig.isDirectory()) {
                return fromConfig.getAbsoluteFile();
            }
        }

        File data = plugin.getDataFolder();
        if (data != null) {
            File pluginsDir = data.getParentFile();
            File serverDir = pluginsDir != null ? pluginsDir.getParentFile() : null;
            File projectRoot = serverDir != null ? serverDir.getParentFile() : null;
            if (projectRoot != null && projectRoot.isDirectory()) {
                return projectRoot.getAbsoluteFile();
            }
        }

        File worldContainer = plugin.getServer().getWorldContainer();
        if (worldContainer != null) {
            File projectRoot = worldContainer.getParentFile();
            if (projectRoot != null && projectRoot.isDirectory()) {
                return projectRoot.getAbsoluteFile();
            }
        }

        throw new IllegalStateException("Nie mozna ustalic katalogu projektu");
    }
}
