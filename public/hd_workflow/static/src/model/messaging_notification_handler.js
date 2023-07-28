/** @odoo-module **/

import { registerPatch } from '@mail/model/model_core';
import { decrement, increment} from '@mail/model/model_field_command';


registerPatch({
    name: 'MessagingNotificationHandler',
    recordMethods: {
        /**
         * @private
         * @param {CustomEvent} ev
         * @param {Object[]} [ev.detail] Notifications coming from the bus.
         * @param {Array|string} ev.detail[i][0] meta-data of the notification.
         * @param {string} ev.detail[i][0][0] name of database this
         *   notification comes from.
         * @param {string} ev.detail[i][0][1] type of notification.
         * @param {integer} ev.detail[i][0][2] usually id of related type
         *   of notification. For instance, with `mail.channel`, this is the id
         *   of the channel.
         * @param {Object} ev.detail[i][1] payload of the notification
         */
        async _handleNotifications({ detail: notifications }) {
            const channelsLeft = new Set(
                notifications
                    .filter(notification => notification.type === 'mail.channel/leave')
                    .map(notification => notification.payload.id)
            );
            const proms = notifications.map(message => {
                if (typeof message === 'object') {
                    switch (message.type) {
                        case 'bus/im_status':
                            return this._handleNotificationBusImStatus(message.payload);
                        case 'ir.attachment/delete':
                            return this._handleNotificationAttachmentDelete(message.payload);
                        case 'mail.channel.member/seen':
                            return this._handleNotificationChannelMemberSeen(message.payload);
                        case 'mail.channel.member/fetched':
                            return this._handleNotificationChannelMemberFetched(message.payload);
                        case 'mail.channel.member/typing_status':
                            return this._handleNotificationChannelMemberTypingStatus(message.payload);
                        case 'mail.channel/new_message':
                            if (channelsLeft.has(message.payload.id)) {
                                /**
                                 * `_handleNotificationChannelMessage` tries to pin the channel,
                                 * which is not desirable if the channel was just left.
                                 * The issue happens because the longpolling request resolves with
                                 * notifications for the channel that was just left (the channels
                                 * to observe are determined when the longpolling starts waiting,
                                 * not when it resolves).
                                 */
                                return;
                            }
                            return this._handleNotificationChannelMessage(message.payload);
                        case 'mail.link.preview/insert':
                            this.messaging.models['LinkPreview'].insert(message.payload);
                            return;
                        case 'mail.link.preview/delete': {
                            const linkPreview = this.messaging.models['LinkPreview'].findFromIdentifyingData(message.payload);
                            if (linkPreview) {
                                linkPreview.delete();
                            }
                            return;
                        }
                        case 'mail.message/delete':
                            return this._handleNotificationMessageDelete(message.payload);
                        case 'mail.message/inbox':
                            return this._handleNotificationNeedaction(message.payload);
                        case 'mail.message/mark_as_read':
                            return this._handleNotificationPartnerMarkAsRead(message.payload);
                        case 'mail.message/notification_update':
                            return this._handleNotificationPartnerMessageNotificationUpdate(message.payload);
                        case 'simple_notification':
                            return this._handleNotificationSimpleNotification(message.payload);
                        case 'mail.message/toggle_star':
                            return this._handleNotificationPartnerToggleStar(message.payload);
                        case 'mail.channel/transient_message':
                            return this._handleNotificationPartnerTransientMessage(message.payload);
                        case 'mail.channel/leave':
                            return this._handleNotificationChannelLeave(message.payload);
                        case 'mail.channel/delete':
                            return this._handleNotificationChannelDelete(message.payload);
                        case 'res.users/connection':
                            return this._handleNotificationPartnerUserConnection(message.payload);
                        case 'mail.activity/updated': {
                            for (const activityMenuView of this.messaging.models['ActivityMenuView'].all()) {
                                if (message.payload.activity_created) {
                                    activityMenuView.update({ extraCount: increment() });
                                }
                                if (message.payload.activity_deleted) {
                                    activityMenuView.update({ extraCount: decrement() });
                                }
                            }
                            return;
                        }
                        case 'hd.personnel.process.record/updated': {
                            for (const todoMenuView of this.messaging.models['TodoMenuView'].all()) {
                                if (message.payload.todo_created) {
                                    todoMenuView.update({ extraCount: increment() });
                                }
                                if (message.payload.todo_deleted) {
                                    todoMenuView.update({ extraCount: decrement() });
                                }
                            }
                            return;
                        }
                        case 'mail.channel/unpin':
                            return this._handleNotificationChannelUnpin(message.payload);
                        case 'mail.channel/joined':
                            return this._handleNotificationChannelJoined(message.payload);
                        case 'mail.channel/last_interest_dt_changed':
                            return this._handleNotificationChannelLastInterestDateTimeChanged(message.payload);
                        case 'mail.channel/legacy_insert':
                            return this.messaging.models['Thread'].insert(this.messaging.models['Thread'].convertData({ model: 'mail.channel', ...message.payload }));
                        case 'mail.channel/insert':
                            return this.messaging.models['Channel'].insert(message.payload);
                        case 'mail.guest/insert':
                            return this.messaging.models['Guest'].insert(message.payload);
                        case 'mail.message/insert':
                            return this.messaging.models['Message'].insert(message.payload);
                        case 'mail.channel.rtc.session/insert':
                            return this.messaging.models['RtcSession'].insert(message.payload);
                        case 'mail.channel.rtc.session/peer_notification':
                            return this._handleNotificationRtcPeerToPeer(message.payload);
                        case 'mail.channel/rtc_sessions_update':
                            return this._handleNotificationRtcSessionUpdate(message.payload);
                        case 'mail.channel.rtc.session/ended':
                            return this._handleNotificationRtcSessionEnded(message.payload);
                        case 'mail.thread/insert':
                            return this.messaging.models['Thread'].insert(message.payload);
                        case 'res.users.settings/insert':
                            return this.messaging.models['res.users.settings'].insert(message.payload);
                        case 'res.users.settings.volumes/insert':
                            return this.messaging.models['res.users.settings.volumes'].insert(message.payload);
                        default:
                            return this._handleNotification(message);
                    }
                }
            });
            await Promise.all(proms);
        },
    },
});
