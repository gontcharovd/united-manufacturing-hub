package postgresql

import (
	"github.com/jackc/pgx/v5/pgconn"
	sharedStructs "github.com/united-manufacturing-hub/united-manufacturing-hub/cmd/kafka-to-postgresql-v2/shared"
	"go.uber.org/zap"
)

func (c *Connection) InsertShiftAdd(msg *sharedStructs.ShiftAddMessage, topic *sharedStructs.TopicDetails) error {
	assetId, err := c.GetOrInsertAsset(topic)
	if err != nil {
		return err
	}

	// Start tx (this shouln't take more then 1 minute)
	ctx, cncl := get1MinuteContext()
	defer cncl()
	tx, err := c.db.Begin(ctx)
	if err != nil {
		return err
	}

	// Insert shift
	var cmdTag pgconn.CommandTag
	cmdTag, err = tx.Exec(ctx, `
		INSERT INTO shifts (assetId, startTime, endTime)
		VALUES ($1, to_timestamp($2 / 1000), to_timestamp($3 / 1000))
		ON CONFLICT ON CONSTRAINT shift_start_asset_uniq
		DO NOTHING;
	`, int(assetId), msg.StartTimeUnixMs, msg.EndTimeUnixMs)

	if err != nil {
		zap.S().Warnf("Error inserting shift: %v (start: %v | end: %v) [%s]", err, msg.StartTimeUnixMs, msg.EndTimeUnixMs, cmdTag)
		zap.S().Debugf("Message: %v (Topic: %v)", msg, topic)
		errR := tx.Rollback(ctx)
		if errR != nil {
			zap.S().Errorf("Error rolling back transaction: %v", errR)
		}
		return err
	}
	return tx.Commit(ctx)
}

func (c *Connection) DeleteShiftByStartTime(msg *sharedStructs.ShiftDeleteMessage, topic *sharedStructs.TopicDetails) error {
	assetId, err := c.GetOrInsertAsset(topic)
	if err != nil {
		return err
	}

	ctx, cncl := get1MinuteContext()
	defer cncl()
	tx, err := c.db.Begin(ctx)
	if err != nil {
		return err
	}

	// Delete shift
	var cmdTag pgconn.CommandTag
	cmdTag, err = tx.Exec(ctx, `
		DELETE FROM shifts
		WHERE assetId = $1 AND startTime = to_timestamp($2 / 1000);
	`, int(assetId), msg.StartTimeUnixMs)

	if err != nil {
		zap.S().Warnf("Error deleting shift: %v (start: %v) [%s]", err, msg.StartTimeUnixMs, cmdTag)
		errR := tx.Rollback(ctx)
		if errR != nil {
			zap.S().Errorf("Error rolling back transaction: %v", errR)
		}
		return err
	}

	return tx.Commit(ctx)
}