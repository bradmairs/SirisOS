import 'dart:convert';

import 'package:shared_preferences/shared_preferences.dart';

import 'siris_context_service.dart';

class ManualContextOverride {
  const ManualContextOverride({
    required this.label,
    required this.domain,
    required this.setAt,
    this.detail,
    this.expiresAt,
  });

  final String label;
  final SirisContextDomain domain;
  final String? detail;
  final DateTime setAt;
  final DateTime? expiresAt;

  bool isExpired(DateTime now) => expiresAt != null && !now.isBefore(expiresAt!);

  Map<String, dynamic> toJson() => {
        'label': label,
        'domain': domain.name,
        'detail': detail,
        'set_at': setAt.toIso8601String(),
        'expires_at': expiresAt?.toIso8601String(),
      };

  factory ManualContextOverride.fromJson(Map<String, dynamic> json) => ManualContextOverride(
        label: json['label'] as String,
        domain: SirisContextDomain.values.firstWhere(
          (value) => value.name == json['domain'],
          orElse: () => SirisContextDomain.personal,
        ),
        detail: json['detail'] as String?,
        setAt: DateTime.parse(json['set_at'] as String),
        expiresAt: json['expires_at'] == null ? null : DateTime.parse(json['expires_at'] as String),
      );
}

/// Lets the user directly assert a current context fact (e.g. "Focused",
/// "Away from home") with optional provenance and an optional expiry --
/// closing the "Manual context override with expiry/provenance" gap ADR 031
/// left open. v1 holds a single active override, matching the roadmap's own
/// singular framing; persisted client-side (SharedPreferences), the same
/// storage boundary every other Context Service provider already lives
/// behind -- there is no server-side context store to persist through.
class ManualContextOverrideService {
  static const _key = 'siris.context.manual_override';

  Future<void> set({
    required String label,
    required SirisContextDomain domain,
    String? detail,
    Duration? expiresIn,
  }) async {
    final now = DateTime.now();
    final override = ManualContextOverride(
      label: label,
      domain: domain,
      detail: detail,
      setAt: now,
      expiresAt: expiresIn == null ? null : now.add(expiresIn),
    );
    final preferences = await SharedPreferences.getInstance();
    await preferences.setString(_key, jsonEncode(override.toJson()));
  }

  Future<void> clear() async {
    final preferences = await SharedPreferences.getInstance();
    await preferences.remove(_key);
  }

  /// Returns the active override, or null if none is set or the stored one
  /// has expired -- an expired override is removed from storage on read
  /// rather than left to linger until something else happens to overwrite it.
  Future<ManualContextOverride?> current() async {
    final preferences = await SharedPreferences.getInstance();
    final raw = preferences.getString(_key);
    if (raw == null) return null;
    final override = ManualContextOverride.fromJson(
      jsonDecode(raw) as Map<String, dynamic>,
    );
    if (override.isExpired(DateTime.now())) {
      await preferences.remove(_key);
      return null;
    }
    return override;
  }
}

class ManualContextOverrideProvider implements SirisContextProvider {
  ManualContextOverrideProvider({ManualContextOverrideService? service})
      : _service = service ?? ManualContextOverrideService();

  final ManualContextOverrideService _service;

  @override
  String get id => 'context.manual_override';

  @override
  Future<List<SirisContextFact>> collect() async {
    final override = await _service.current();
    if (override == null) return const [];
    return [
      SirisContextFact(
        id: 'manual.override',
        label: override.label,
        domain: override.domain,
        // Outranks every provider-derived fact (the highest existing
        // priority, UPS power events, is 100) so a manual assertion always
        // wins as the primary context -- the user said so directly, that
        // beats anything inferred.
        priority: 200,
        source: 'manual',
        detail: override.detail,
        observedAt: override.setAt,
      ),
    ];
  }
}
