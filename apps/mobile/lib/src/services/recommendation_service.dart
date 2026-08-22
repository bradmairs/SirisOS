import 'dart:convert';

import 'package:http/http.dart' as http;

import '../config/api_config.dart';
import 'auth_service.dart';

enum RecommendationStatus { pending, dismissed, acted }

extension RecommendationStatusValue on RecommendationStatus {
  String get apiValue => name;

  static RecommendationStatus fromApiValue(String value) =>
      RecommendationStatus.values.firstWhere(
        (item) => item.apiValue == value,
        orElse: () => RecommendationStatus.pending,
      );
}

class RecommendationRecord {
  const RecommendationRecord({
    required this.id,
    required this.title,
    required this.rationale,
    required this.severity,
    required this.evidenceSource,
    required this.evidenceId,
    required this.suggestedAction,
    required this.capabilityId,
    required this.capabilityParams,
    required this.synthesizedRationale,
    required this.status,
    required this.createdAt,
    required this.updatedAt,
  });

  final String id;
  final String title;
  final String rationale;
  final String severity;
  final String evidenceSource;
  final String evidenceId;
  final String suggestedAction;
  final String? capabilityId;
  final Map<String, String>? capabilityParams;
  final String? synthesizedRationale;
  final RecommendationStatus status;
  final DateTime createdAt;
  final DateTime updatedAt;

  /// The synthesized (Ollama-rephrased) rationale when available, falling
  /// back to the deterministic one -- same additive-not-replacement contract
  /// as Coach's `synthesizedHeadline ?? headline` (ADR 090).
  String get displayRationale => synthesizedRationale ?? rationale;

  factory RecommendationRecord.fromJson(Map<String, dynamic> json) =>
      RecommendationRecord(
        id: json['id'] as String,
        title: json['title'] as String,
        rationale: json['rationale'] as String,
        severity: json['severity'] as String,
        evidenceSource: json['evidence_source'] as String,
        evidenceId: json['evidence_id'] as String,
        suggestedAction: json['suggested_action'] as String,
        capabilityId: json['capability_id'] as String?,
        capabilityParams: (json['capability_params'] as Map<String, dynamic>?)
            ?.map((key, value) => MapEntry(key, value as String)),
        synthesizedRationale: json['synthesized_rationale'] as String?,
        status: RecommendationStatusValue.fromApiValue(
          json['status'] as String,
        ),
        createdAt: DateTime.parse(json['created_at'] as String),
        updatedAt: DateTime.parse(json['updated_at'] as String),
      );
}

class RecommendationService {
  Future<List<RecommendationRecord>> list({
    RecommendationStatus? status,
  }) async {
    final uri = Uri.parse('${ApiConfig.baseUrl}/api/v1/recommendations')
        .replace(
          queryParameters: status != null ? {'status': status.apiValue} : null,
        );
    final response = await http
        .get(uri, headers: AuthService.authorizationHeaders)
        .timeout(const Duration(seconds: 12));
    if (response.statusCode != 200) {
      throw RecommendationServiceException(
        'Unable to load recommendations (${response.statusCode}).',
      );
    }
    final decoded = jsonDecode(response.body);
    if (decoded is! List) {
      throw const RecommendationServiceException(
        'Recommendations response was not a list.',
      );
    }
    return decoded
        .whereType<Map<String, dynamic>>()
        .map(RecommendationRecord.fromJson)
        .toList(growable: false);
  }

  Future<RecommendationRecord> updateStatus(
    String id,
    RecommendationStatus status,
  ) async {
    final response = await http
        .patch(
          Uri.parse('${ApiConfig.baseUrl}/api/v1/recommendations/$id'),
          headers: {
            ...AuthService.authorizationHeaders,
            'Content-Type': 'application/json',
          },
          body: jsonEncode({'status': status.apiValue}),
        )
        .timeout(const Duration(seconds: 12));
    if (response.statusCode != 200) {
      throw RecommendationServiceException(
        'Unable to update recommendation (${response.statusCode}).',
      );
    }
    return RecommendationRecord.fromJson(
      jsonDecode(response.body) as Map<String, dynamic>,
    );
  }
}

class RecommendationServiceException implements Exception {
  const RecommendationServiceException(this.message);
  final String message;

  @override
  String toString() => message;
}
