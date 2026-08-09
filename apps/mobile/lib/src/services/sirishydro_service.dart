import 'dart:convert';

import 'package:http/http.dart' as http;

import '../config/api_config.dart';
import 'auth_service.dart';

class SirisHydroEvidenceItem {
  const SirisHydroEvidenceItem({
    required this.documentId,
    required this.title,
    required this.authority,
    required this.page,
    required this.citation,
    required this.excerpt,
    required this.score,
    this.reference,
    this.edition,
  });

  final String documentId;
  final String title;
  final String authority;
  final String? reference;
  final String? edition;
  final int page;
  final String citation;
  final String excerpt;
  final int score;

  factory SirisHydroEvidenceItem.fromJson(Map<String, dynamic> json) =>
      SirisHydroEvidenceItem(
        documentId: json['document_id'] as String,
        title: json['title'] as String,
        authority: json['authority'] as String,
        reference: json['reference'] as String?,
        edition: json['edition'] as String?,
        page: (json['page'] as num).toInt(),
        citation: json['citation'] as String,
        excerpt: json['excerpt'] as String? ?? '',
        score: (json['score'] as num?)?.toInt() ?? 0,
      );
}

class SirisHydroEvidencePacket {
  const SirisHydroEvidencePacket({
    required this.question,
    required this.sufficientEvidence,
    required this.evidence,
    required this.contextText,
    required this.guidance,
    this.synthesizedAnswer,
  });

  final String question;
  final bool sufficientEvidence;
  final List<SirisHydroEvidenceItem> evidence;
  final String contextText;
  final String guidance;
  final String? synthesizedAnswer;

  factory SirisHydroEvidencePacket.fromJson(Map<String, dynamic> json) {
    final rawEvidence = json['evidence'] as List<dynamic>? ?? const [];
    return SirisHydroEvidencePacket(
      question: json['question'] as String? ?? '',
      sufficientEvidence: json['sufficient_evidence'] == true,
      evidence: rawEvidence
          .whereType<Map<String, dynamic>>()
          .map(SirisHydroEvidenceItem.fromJson)
          .toList(growable: false),
      contextText: json['context_text'] as String? ?? '',
      guidance: json['guidance'] as String? ?? '',
      synthesizedAnswer: json['synthesized_answer'] as String?,
    );
  }
}

class SirisHydroService {
  Future<SirisHydroEvidencePacket> retrieveEvidence(String question) async {
    final uri = Uri.parse(
      '${ApiConfig.baseUrl}/api/v1/engineering/sirishydro/evidence',
    ).replace(queryParameters: {'question': question.trim()});
    final response = await http
        .get(uri, headers: AuthService.authorizationHeaders)
        .timeout(const Duration(seconds: 15));
    if (response.statusCode != 200) {
      String detail = 'SirisHydro evidence retrieval failed (${response.statusCode}).';
      try {
        final decoded = jsonDecode(response.body) as Map<String, dynamic>;
        if (decoded['detail'] is String) detail = decoded['detail'] as String;
      } catch (_) {}
      throw SirisHydroException(detail);
    }
    return SirisHydroEvidencePacket.fromJson(
      jsonDecode(response.body) as Map<String, dynamic>,
    );
  }
}

class SirisHydroException implements Exception {
  const SirisHydroException(this.message);
  final String message;

  @override
  String toString() => message;
}
