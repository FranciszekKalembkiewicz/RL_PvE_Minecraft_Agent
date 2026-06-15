package pl.pwr.rl.wavearena;

import com.google.gson.Gson;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import org.bukkit.entity.EntityType;
import org.bukkit.entity.LivingEntity;
import org.bukkit.entity.Player;

import java.io.BufferedReader;
import java.io.BufferedWriter;
import java.io.IOException;
import java.io.InputStreamReader;
import java.io.OutputStreamWriter;
import java.net.ServerSocket;
import java.net.Socket;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.atomic.AtomicBoolean;

public class BridgeServer implements Runnable {

    private final WaveArenaPlugin plugin;
    private final Gson gson = new Gson();
    private final AtomicBoolean running = new AtomicBoolean(false);
    private ServerSocket serverSocket;
    private Thread thread;

    public BridgeServer(WaveArenaPlugin plugin) {
        this.plugin = plugin;
    }

    public void start() {
        if (running.getAndSet(true)) return;
        thread = new Thread(this, "WaveArena-Bridge");
        thread.setDaemon(true);
        thread.start();
    }

    public void stop() {
        running.set(false);
        if (serverSocket != null && !serverSocket.isClosed()) {
            try {
                serverSocket.close();
            } catch (IOException ignored) {
            }
        }
        if (thread != null) {
            thread.interrupt();
        }
    }

    @Override
    public void run() {
        int port = plugin.getArenaConfig().bridgePort;
        try {
            serverSocket = new ServerSocket(port);
            plugin.getLogger().info("Bridge TCP listening on port " + port);
            while (running.get()) {
                try {
                    Socket client = serverSocket.accept();
                    Thread t = new Thread(() -> handleClient(client), "WaveArena-Client");
                    t.setDaemon(true);
                    t.start();
                } catch (IOException e) {
                    if (running.get()) {
                        plugin.getLogger().warning("Bridge accept error: " + e.getMessage());
                    }
                }
            }
        } catch (IOException e) {
            plugin.getLogger().severe("Bridge failed to bind port " + port + ": " + e.getMessage());
        }
    }

    private void handleClient(Socket socket) {
        try (
                Socket s = socket;
                BufferedReader in = new BufferedReader(new InputStreamReader(s.getInputStream(), StandardCharsets.UTF_8));
                BufferedWriter out = new BufferedWriter(new OutputStreamWriter(s.getOutputStream(), StandardCharsets.UTF_8))
        ) {
            String line;
            while ((line = in.readLine()) != null) {
                final String commandLine = line;
                JsonObject response = plugin.getServer().getScheduler().callSyncMethod(plugin, () -> {
                    try {
                        return handleCommand(commandLine);
                    } catch (Exception ex) {
                        JsonObject err = new JsonObject();
                        err.addProperty("ok", false);
                        err.addProperty("error", ex.getMessage());
                        return err;
                    }
                }).get();

                out.write(gson.toJson(response));
                out.write("\n");
                out.flush();
            }
        } catch (Exception e) {
            plugin.getLogger().fine("Bridge client closed: " + e.getMessage());
        }
    }

    private JsonObject handleCommand(String line) {
        JsonObject req = JsonParser.parseString(line.trim()).getAsJsonObject();
        String cmd = req.has("cmd") ? req.get("cmd").getAsString() : "";

        return switch (cmd) {
            case "reset" -> {
                plugin.getWaveManager().resetEpisode();
                yield buildState(true, null);
            }
            case "step" -> {
                int action = req.has("action") ? req.get("action").getAsInt() : 5;
                WaveManager.StepResult result = plugin.getWaveManager().executeStep(action);
                if (!result.success) {
                    yield buildState(false, result.error);
                }
                yield buildState(true, null);
            }
            case "status" -> buildState(true, null);
            case "reload" -> {
                plugin.getArenaConfig().reload();
                JsonObject o = buildState(true, null);
                o.addProperty("config_reloaded", true);
                o.addProperty("skeleton_face_target", plugin.getArenaConfig().skeletonFaceTarget);
                o.addProperty("skeleton_move_toward", plugin.getArenaConfig().skeletonMoveTowardTarget);
                com.google.gson.JsonArray seq = new com.google.gson.JsonArray();
                for (EntityType t : plugin.getArenaConfig().waveMobSequence) {
                    seq.add(t.name());
                }
                o.add("wave_mob_sequence", seq);
                yield o;
            }
            default -> {
                JsonObject o = new JsonObject();
                o.addProperty("ok", false);
                o.addProperty("error", "unknown_cmd");
                yield o;
            }
        };
    }

    private JsonObject buildState(boolean ok, String error) {
        JsonObject o = new JsonObject();
        o.addProperty("ok", ok);
        if (error != null) o.addProperty("error", error);

        WaveManager wm = plugin.getWaveManager();
        ArenaConfig cfg = plugin.getArenaConfig();

        o.addProperty("wave", wm.currentWave);
        o.addProperty("max_wave", wm.maxWaveReached);
        o.addProperty("alive_mobs", wm.countAliveMobs());
        o.addProperty("episode_done", wm.episodeDone);
        o.addProperty("wave_cleared", wm.waveClearedThisStep);
        o.addProperty("wave_failed", wm.waveFailed);
        o.addProperty("step", wm.episodeStep);
        o.addProperty("kills_this_step", wm.killsThisStep);
        o.addProperty("damage_dealt", wm.damageDealtThisStep);
        o.addProperty("damage_taken", wm.damageTakenThisStep);
        o.addProperty("arena_radius", cfg.radius);
        if (wm.getCurrentWaveMobType() != null) {
            o.addProperty("wave_mob_type", wm.getCurrentWaveMobType().name());
        }

        JsonObject center = new JsonObject();
        center.addProperty("x", cfg.centerX);
        center.addProperty("y", cfg.centerY);
        center.addProperty("z", cfg.centerZ);
        o.add("arena_center", center);

        Player agent = wm.getAgent();
        if (agent != null) {
            o.addProperty("agent_hp", agent.getHealth());
            o.addProperty("agent_max_hp", cfg.agentMaxHp);
            JsonObject pos = new JsonObject();
            pos.addProperty("x", agent.getLocation().getX());
            pos.addProperty("y", agent.getLocation().getY());
            pos.addProperty("z", agent.getLocation().getZ());
            o.add("agent_pos", pos);
            o.addProperty("agent_yaw", agent.getLocation().getYaw());
        } else {
            o.addProperty("agent_hp", 0);
            o.addProperty("agent_max_hp", cfg.agentMaxHp);
        }

        com.google.gson.JsonArray mobs = new com.google.gson.JsonArray();
        for (LivingEntity mob : wm.aliveMobs()) {
            JsonObject m = new JsonObject();
            m.addProperty("hp", mob.getHealth());
            double maxHp = mob.getAttribute(org.bukkit.attribute.Attribute.GENERIC_MAX_HEALTH) != null
                    ? mob.getAttribute(org.bukkit.attribute.Attribute.GENERIC_MAX_HEALTH).getValue()
                    : cfg.agentMaxHp;
            m.addProperty("max_hp", maxHp);
            m.addProperty("x", mob.getLocation().getX());
            m.addProperty("y", mob.getLocation().getY());
            m.addProperty("z", mob.getLocation().getZ());
            m.addProperty("type", mob.getType().name());
            mobs.add(m);
        }
        o.add("mobs", mobs);
        return o;
    }
}
