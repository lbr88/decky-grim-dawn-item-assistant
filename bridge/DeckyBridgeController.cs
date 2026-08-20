using IAGrim.UI.Misc;
using IAGrim.Utilities;
using log4net;
using Newtonsoft.Json;
using System.Globalization;
using System.Text;

namespace IAGrim.UI.Controller {
    /// <summary>
    /// A deliberately narrow, local-only bridge for the Decky plugin.
    ///
    /// The bridge accepts only a PlayerItem id from a fixed directory beneath
    /// Item Assistant's own data folder. It invokes ItemTransferController on
    /// the UI/SQL thread so normal stash, database and cloud-sync behavior is
    /// preserved. It exposes no network listener, command execution or paths.
    /// </summary>
    internal sealed class DeckyBridgeController : IDisposable {
        private const int BridgeVersion = 1;
        private const long MaximumRequestBytes = 4096;
        private static readonly TimeSpan MaximumRequestAge = TimeSpan.FromSeconds(30);
        private static readonly TimeSpan StaleFileAge = TimeSpan.FromMinutes(5);
        private static readonly ILog Logger = LogManager.GetLogger(typeof(DeckyBridgeController));

        private readonly ItemTransferController _transferController;
        private readonly System.Windows.Forms.Timer _timer;
        private readonly string _root;
        private readonly string _requests;
        private readonly string _responses;
        private readonly string _status;
        private DateTime _lastCleanupUtc = DateTime.MinValue;
        private bool _processing;
        private bool _disposed;

        public DeckyBridgeController(ItemTransferController transferController) {
            _transferController = transferController;
            _root = GlobalPaths.DeckyBridge;
            _requests = Path.Combine(_root, "requests");
            _responses = Path.Combine(_root, "responses");
            _status = Path.Combine(_root, "status.json");

            Directory.CreateDirectory(_requests);
            Directory.CreateDirectory(_responses);
            CleanupStaleFiles();
            WriteStatus();

            _timer = new System.Windows.Forms.Timer { Interval = 250 };
            _timer.Tick += Poll;
            _timer.Start();
            Logger.Info("Decky item transfer bridge started");
        }

        private void Poll(object? sender, EventArgs args) {
            if (_processing || _disposed) {
                return;
            }

            _processing = true;
            try {
                foreach (var request in new DirectoryInfo(_requests)
                    .EnumerateFiles("*.json")
                    .OrderBy(file => file.CreationTimeUtc)
                    .Take(4)) {
                    ProcessRequest(request);
                }

                if (DateTime.UtcNow - _lastCleanupUtc > TimeSpan.FromMinutes(1)) {
                    CleanupStaleFiles();
                }
            }
            catch (Exception ex) {
                Logger.Warn("Decky bridge polling failed", ex);
            }
            finally {
                _processing = false;
            }
        }

        private void ProcessRequest(FileInfo requestFile) {
            string requestId = Path.GetFileNameWithoutExtension(requestFile.Name);
            if (!Guid.TryParseExact(requestId, "D", out _)) {
                TryDelete(requestFile.FullName);
                return;
            }

            string processingPath = requestFile.FullName + ".processing";
            try {
                File.Move(requestFile.FullName, processingPath);
            }
            catch (IOException) {
                return;
            }

            BridgeResponse response;
            try {
                response = ExecuteRequest(processingPath, requestId);
            }
            catch (Exception ex) {
                Logger.Warn("Decky bridge request failed", ex);
                response = BridgeResponse.Failure(requestId, "Item Assistant could not process that transfer");
            }

            try {
                WriteJsonAtomic(Path.Combine(_responses, requestId + ".json"), response);
            }
            catch (Exception ex) {
                Logger.Warn("Could not write Decky bridge response", ex);
            }
            finally {
                TryDelete(processingPath);
            }
        }

        private BridgeResponse ExecuteRequest(string path, string requestId) {
            var file = new FileInfo(path);
            if (!file.Exists || file.Length <= 0 || file.Length > MaximumRequestBytes) {
                return BridgeResponse.Failure(requestId, "The Decky transfer request was invalid");
            }

            var request = JsonConvert.DeserializeObject<BridgeRequest>(File.ReadAllText(path));
            long now = DateTimeOffset.UtcNow.ToUnixTimeSeconds();
            if (request == null ||
                request.Version != BridgeVersion ||
                !string.Equals(request.RequestId, requestId, StringComparison.Ordinal) ||
                !string.Equals(request.Action, "transfer", StringComparison.Ordinal) ||
                request.PlayerItemId <= 0 ||
                request.CreatedAt < now - (long)MaximumRequestAge.TotalSeconds ||
                request.CreatedAt > now + (long)MaximumRequestAge.TotalSeconds) {
                return BridgeResponse.Failure(requestId, "The Decky transfer request was invalid");
            }

            var transferArgs = new StashTransferEventArgs(
                new object[] {
                    "PI",
                    request.PlayerItemId.ToString(CultureInfo.InvariantCulture),
                    "-",
                    "-",
                    "-",
                    false
                },
                false
            );

            // The timer runs on Item Assistant's UI thread, which is also its SQL thread.
            // Do not show the cross-mod stash picker for a non-interactive Decky request.
            _transferController.TransferItem(transferArgs, false);
            if (!transferArgs.IsSuccessful) {
                return BridgeResponse.Failure(requestId, "Item Assistant could not transfer that item");
            }

            string noun = transferArgs.NumTransferred == 1 ? "item" : "items";
            return BridgeResponse.Success(
                requestId,
                $"Transferred {transferArgs.NumTransferred} {noun} to Grim Dawn",
                transferArgs.NumTransferred
            );
        }

        private void WriteStatus() {
            WriteJsonAtomic(
                _status,
                new BridgeStatus {
                    Version = BridgeVersion,
                    Ready = true,
                    Pid = Environment.ProcessId
                }
            );
        }

        private void CleanupStaleFiles() {
            _lastCleanupUtc = DateTime.UtcNow;
            CleanupDirectory(_requests);
            CleanupDirectory(_responses);
        }

        private static void CleanupDirectory(string directory) {
            DateTime cutoff = DateTime.UtcNow - StaleFileAge;
            try {
                foreach (var file in new DirectoryInfo(directory).EnumerateFiles()) {
                    if (file.LastWriteTimeUtc < cutoff) {
                        TryDelete(file.FullName);
                    }
                }
            }
            catch (Exception ex) {
                Logger.Debug("Decky bridge cleanup skipped", ex);
            }
        }

        private static void WriteJsonAtomic(string destination, object value) {
            string directory = Path.GetDirectoryName(destination)!;
            Directory.CreateDirectory(directory);
            string temporary = Path.Combine(
                directory,
                "." + Path.GetFileName(destination) + "." + Guid.NewGuid().ToString("N") + ".tmp"
            );
            try {
                string json = JsonConvert.SerializeObject(value, Formatting.None);
                File.WriteAllText(temporary, json, new UTF8Encoding(false));
                File.Move(temporary, destination, true);
            }
            finally {
                TryDelete(temporary);
            }
        }

        private static void TryDelete(string path) {
            try {
                File.Delete(path);
            }
            catch (IOException) {
            }
            catch (UnauthorizedAccessException) {
            }
        }

        public void Dispose() {
            if (_disposed) {
                return;
            }
            _disposed = true;
            _timer.Stop();
            _timer.Tick -= Poll;
            _timer.Dispose();
            TryDelete(_status);
            Logger.Info("Decky item transfer bridge stopped");
        }

        private sealed class BridgeRequest {
            [JsonProperty("version")]
            public int Version { get; set; }

            [JsonProperty("requestId")]
            public string? RequestId { get; set; }

            [JsonProperty("action")]
            public string? Action { get; set; }

            [JsonProperty("playerItemId")]
            public long PlayerItemId { get; set; }

            [JsonProperty("createdAt")]
            public long CreatedAt { get; set; }
        }

        private sealed class BridgeStatus {
            [JsonProperty("version")]
            public int Version { get; set; }

            [JsonProperty("ready")]
            public bool Ready { get; set; }

            [JsonProperty("pid")]
            public int Pid { get; set; }
        }

        private sealed class BridgeResponse {
            [JsonProperty("version")]
            public int Version { get; set; } = BridgeVersion;

            [JsonProperty("requestId")]
            public string RequestId { get; set; } = string.Empty;

            [JsonProperty("ok")]
            public bool Ok { get; set; }

            [JsonProperty("message")]
            public string Message { get; set; } = string.Empty;

            [JsonProperty("numTransferred")]
            public int NumTransferred { get; set; }

            public static BridgeResponse Success(string requestId, string message, int count) {
                return new BridgeResponse {
                    RequestId = requestId,
                    Ok = true,
                    Message = message,
                    NumTransferred = count
                };
            }

            public static BridgeResponse Failure(string requestId, string message) {
                return new BridgeResponse {
                    RequestId = requestId,
                    Ok = false,
                    Message = message
                };
            }
        }
    }
}
