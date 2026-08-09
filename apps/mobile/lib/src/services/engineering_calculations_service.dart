import 'dart:convert';

import 'package:http/http.dart' as http;

import '../config/api_config.dart';
import 'auth_service.dart';

class CalculationResultItem {
  const CalculationResultItem({required this.label, required this.value});
  final String label;
  final String value;

  factory CalculationResultItem.fromJson(Map<String, dynamic> json) => CalculationResultItem(
        label: json['label'] as String,
        value: json['value'] as String,
      );

  Map<String, dynamic> toJson() => {'label': label, 'value': value};
}

class SavedCalculation {
  const SavedCalculation({
    required this.id,
    required this.calculatorId,
    required this.title,
    required this.inputs,
    required this.results,
    required this.notes,
    required this.createdAt,
    this.citedStandardId,
    this.citedStandardLabel,
  });

  final String id;
  final String calculatorId;
  final String title;
  final Map<String, double> inputs;
  final List<CalculationResultItem> results;
  final String notes;
  final DateTime createdAt;
  final String? citedStandardId;
  final String? citedStandardLabel;

  factory SavedCalculation.fromJson(Map<String, dynamic> json) => SavedCalculation(
        id: json['id'] as String,
        calculatorId: json['calculator_id'] as String,
        title: json['title'] as String,
        inputs: (json['inputs'] as Map<String, dynamic>? ?? const {})
            .map((key, value) => MapEntry(key, (value as num).toDouble())),
        results: (json['results'] as List<dynamic>? ?? const [])
            .whereType<Map<String, dynamic>>()
            .map(CalculationResultItem.fromJson)
            .toList(growable: false),
        notes: json['notes'] as String? ?? '',
        createdAt: DateTime.parse(json['created_at'] as String),
        citedStandardId: json['cited_standard_id'] as String?,
        citedStandardLabel: json['cited_standard_label'] as String?,
      );
}

class EngineeringCalculationsService {
  Future<List<SavedCalculation>> list() async {
    final response = await http
        .get(
          Uri.parse('${ApiConfig.baseUrl}/api/v1/engineering/calculations'),
          headers: AuthService.authorizationHeaders,
        )
        .timeout(const Duration(seconds: 12));
    if (response.statusCode != 200) {
      throw EngineeringCalculationsException('Unable to load saved calculations (${response.statusCode}).');
    }
    final body = jsonDecode(response.body) as Map<String, dynamic>;
    return (body['calculations'] as List<dynamic>? ?? const [])
        .whereType<Map<String, dynamic>>()
        .map(SavedCalculation.fromJson)
        .toList(growable: false);
  }

  Future<SavedCalculation> save({
    required String calculatorId,
    required String title,
    required Map<String, double> inputs,
    required List<CalculationResultItem> results,
    String notes = '',
    String? citedStandardId,
  }) async {
    final response = await http
        .post(
          Uri.parse('${ApiConfig.baseUrl}/api/v1/engineering/calculations'),
          headers: {
            ...AuthService.authorizationHeaders,
            'Content-Type': 'application/json',
          },
          body: jsonEncode({
            'calculator_id': calculatorId,
            'title': title,
            'inputs': inputs,
            'results': results.map((item) => item.toJson()).toList(growable: false),
            'notes': notes,
            if (citedStandardId != null) 'cited_standard_id': citedStandardId,
          }),
        )
        .timeout(const Duration(seconds: 12));
    if (response.statusCode != 201) {
      throw EngineeringCalculationsException('Unable to save calculation (${response.statusCode}).');
    }
    return SavedCalculation.fromJson(jsonDecode(response.body) as Map<String, dynamic>);
  }

  Future<void> delete(String id) async {
    final response = await http
        .delete(
          Uri.parse('${ApiConfig.baseUrl}/api/v1/engineering/calculations/$id'),
          headers: AuthService.authorizationHeaders,
        )
        .timeout(const Duration(seconds: 12));
    if (response.statusCode != 204) {
      throw EngineeringCalculationsException('Unable to delete calculation (${response.statusCode}).');
    }
  }
}

class EngineeringCalculationsException implements Exception {
  const EngineeringCalculationsException(this.message);
  final String message;

  @override
  String toString() => message;
}
