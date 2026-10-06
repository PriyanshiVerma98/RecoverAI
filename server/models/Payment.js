const mongoose = require('mongoose');

const PAYMENT_METHODS = ['card', 'upi', 'netbanking', 'wallet'];
const PAYMENT_STATUSES = ['success', 'failed', 'pending'];
const FAILURE_REASONS = [
  'insufficient_funds',
  'expired_card',
  'bank_declined',
  'gateway_error',
  'incorrect_details',
  'network_error',
  'authentication_failed',
  'unknown',
];
const RECOVERY_STATUSES = [
  'not_started',
  'recommended',
  'retry_simulated',
  'reminder_sent',
  'update_requested',
  'recovered_simulated',
  'ignored',
];
const ACTIONS = [
  'retry_payment',
  'send_reminder',
  'request_payment_method_update',
  'wait_and_retry',
  'contact_customer',
  'do_not_retry',
  'escalate',
];

const aiAnalysisSchema = new mongoose.Schema(
  {
    diagnosis: String,
    recoverability: { type: String, enum: ['high', 'medium', 'low'] },
    recommendedAction: { type: String, enum: ACTIONS },
    priority: { type: String, enum: ['high', 'medium', 'low'] },
    reasoning: String,
    customerMessage: String,
    confidence: { type: Number, min: 0, max: 1 },
    source: { type: String, enum: ['llm', 'fallback'] },
    ruleOverride: { type: Boolean, default: false },
    inputHash: String,
    analyzedAt: Date,
  },
  { _id: false }
);

const factorSchema = new mongoose.Schema(
  {
    label: String,
    impact: { type: String, enum: ['positive', 'negative'] },
  },
  { _id: false }
);

const paymentSchema = new mongoose.Schema(
  {
    paymentId: { type: String, required: true, unique: true, index: true },
    merchantId: { type: mongoose.Schema.Types.ObjectId, ref: 'User', required: true, index: true },
    customerId: { type: String, required: true, index: true },
    amount: { type: Number, required: true, min: 0 },
    currency: { type: String, default: 'INR' },
    paymentMethod: { type: String, enum: PAYMENT_METHODS, required: true },
    paymentStatus: { type: String, enum: PAYMENT_STATUSES, required: true, index: true },
    failureReason: { type: String, enum: [...FAILURE_REASONS, null], default: null },
    customerType: { type: String, enum: ['new', 'returning', 'vip'] },
    previousSuccessfulPayments: { type: Number, default: 0 },
    previousFailedPayments: { type: Number, default: 0 },
    previousRecoveryAttempts: { type: Number, default: 0 },
    subscriptionStatus: { type: String, enum: ['active', 'past_due', 'cancelled', 'none'] },
    customerLifetimeValue: { type: Number, default: 0 },
    timestamp: { type: Date, required: true, index: true },
    lastAttemptAt: Date,

    recoveryStatus: { type: String, enum: RECOVERY_STATUSES, default: 'not_started', index: true },
    recoveryProbability: { type: Number, min: 0, max: 1 },
    recoveryScore: { type: Number, min: 0, max: 100 },
    recoveryPriority: { type: String, enum: ['high', 'medium', 'low'], index: true },
    recommendedAction: { type: String, enum: ACTIONS },
    aiExplanation: String,
    factors: [factorSchema],
    aiAnalysis: aiAnalysisSchema,
  },
  { timestamps: true }
);

paymentSchema.index({ merchantId: 1, paymentStatus: 1, recoveryPriority: 1 });
paymentSchema.index({ merchantId: 1, timestamp: -1 });

module.exports = mongoose.model('Payment', paymentSchema);
module.exports.ENUMS = {
  PAYMENT_METHODS,
  PAYMENT_STATUSES,
  FAILURE_REASONS,
  RECOVERY_STATUSES,
  ACTIONS,
};