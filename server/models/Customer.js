const mongoose = require('mongoose');

const customerSchema = new mongoose.Schema(
  {
    customerId: { type: String, required: true, unique: true, index: true },
    merchantId: { type: mongoose.Schema.Types.ObjectId, ref: 'User', required: true, index: true },
    name: { type: String, required: true, trim: true },
    customerType: { type: String, enum: ['new', 'returning', 'vip'], default: 'new' },
    subscriptionStatus: {
      type: String,
      enum: ['active', 'past_due', 'cancelled', 'none'],
      default: 'none',
    },
    lifetimeValue: { type: Number, default: 0, min: 0 },
    previousSuccessfulPayments: { type: Number, default: 0, min: 0 },
    previousFailedPayments: { type: Number, default: 0, min: 0 },
  },
  { timestamps: true }
);

module.exports = mongoose.model('Customer', customerSchema);