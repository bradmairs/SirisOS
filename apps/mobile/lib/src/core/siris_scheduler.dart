import 'dart:async';

class SirisScheduledJob {
  SirisScheduledJob({
    required this.id,
    required this.interval,
    required this.run,
  });

  final String id;
  final Duration interval;
  final Future<void> Function() run;
  Timer? _timer;
  bool _running = false;

  void start() {
    _timer?.cancel();
    _timer = Timer.periodic(interval, (_) => execute());
  }

  Future<void> execute() async {
    if (_running) return;
    _running = true;
    try {
      await run();
    } finally {
      _running = false;
    }
  }

  void stop() {
    _timer?.cancel();
    _timer = null;
  }
}

class SirisScheduler {
  SirisScheduler._();

  static final SirisScheduler instance = SirisScheduler._();
  final Map<String, SirisScheduledJob> _jobs = {};

  void register(SirisScheduledJob job) {
    _jobs.remove(job.id)?.stop();
    _jobs[job.id] = job;
    job.start();
  }

  void unregister(String id) => _jobs.remove(id)?.stop();

  Future<void> runNow(String id) async => _jobs[id]?.execute();

  void dispose() {
    for (final job in _jobs.values) {
      job.stop();
    }
    _jobs.clear();
  }
}
