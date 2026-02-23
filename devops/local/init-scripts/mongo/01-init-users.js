// MongoDB initialization script for Cadence
// This script runs automatically when the database is first created

print('Starting Cadence MongoDB initialization...');

// Switch to admin database
db = db.getSiblingDB('admin');

// Create cadence application user with read/write access to all databases
db.createUser({
  user: 'cadence_app',
  pwd: 'cadence_app_password',
  roles: [
    { role: 'readWriteAnyDatabase', db: 'admin' },
    { role: 'dbAdminAnyDatabase', db: 'admin' }
  ]
});

print('Created application user: cadence_app');

// Create a sample database for organization (per-tenant pattern)
// In production, these are created dynamically per organization
db = db.getSiblingDB('cadence_sample_org');

db.createCollection('conversations', {
  validator: {
    $jsonSchema: {
      bsonType: 'object',
      required: ['conversation_id', 'org_id', 'user_id', 'created_at'],
      properties: {
        conversation_id: {
          bsonType: 'string',
          description: 'Unique conversation identifier'
        },
        org_id: {
          bsonType: 'string',
          description: 'Organization identifier'
        },
        user_id: {
          bsonType: 'string',
          description: 'User identifier'
        },
        instance_id: {
          bsonType: 'string',
          description: 'Orchestrator instance identifier'
        },
        created_at: {
          bsonType: 'date',
          description: 'Conversation creation timestamp'
        },
        updated_at: {
          bsonType: 'date',
          description: 'Last message timestamp'
        }
      }
    }
  }
});

db.createCollection('messages', {
  validator: {
    $jsonSchema: {
      bsonType: 'object',
      required: ['message_id', 'conversation_id', 'role', 'content', 'timestamp'],
      properties: {
        message_id: {
          bsonType: 'string',
          description: 'Unique message identifier'
        },
        conversation_id: {
          bsonType: 'string',
          description: 'Parent conversation identifier'
        },
        role: {
          enum: ['human', 'ai', 'system', 'tool'],
          description: 'Message role'
        },
        content: {
          bsonType: 'string',
          description: 'Message content'
        },
        timestamp: {
          bsonType: 'date',
          description: 'Message timestamp'
        },
        metadata: {
          bsonType: 'object',
          description: 'Additional message metadata'
        }
      }
    }
  }
});

// Create indexes for performance
db.conversations.createIndex({ conversation_id: 1 }, { unique: true });
db.conversations.createIndex({ org_id: 1, user_id: 1 });
db.conversations.createIndex({ created_at: -1 });

db.messages.createIndex({ message_id: 1 }, { unique: true });
db.messages.createIndex({ conversation_id: 1, timestamp: 1 });
db.messages.createIndex({ timestamp: -1 });

print('Created sample collections with indexes');
print('Cadence MongoDB initialization completed successfully');
